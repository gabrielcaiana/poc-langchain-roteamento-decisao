"""Avaliação do fluxo de assinatura: intenção e, em seguida, capability.
Não executa a capability (não muda a base fictícia). Uso:
python scripts/avaliar_capabilities.py --provedores msd1 jev llm
"""
import argparse, json, pathlib, statistics, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from langchain_core.messages import AIMessage, HumanMessage
from roteador.capabilities import PERGUNTA as PERGUNTA_CAPABILITY, REGISTRO, politica_capability
from roteador.config import CONFIG
from roteador.decisao import ClassificadorIntencao, criar_provedor
from roteador.grafo import politica_roteamento
from roteador.llm import criar_llm
from roteador.orcamento import Ledger

ROOT = pathlib.Path(__file__).resolve().parents[1]


def mensagens(item):
    ms = [HumanMessage(h["cliente"]) if "cliente" in h else AIMessage(h["atendente"]) for h in item["historico"]]
    return ms + [HumanMessage(item["mensagem"])]


def _taxa(acertos, total):
    return round(acertos / total, 3) if total else None


def _caminho_completo(linha):
    """O que o grafo faria: intenção certa e, na assinatura, capability certa.
    Nos ambíguos, acerto é entrar em assinatura e não executar."""
    if linha["rotulo_intencao"] != "assinatura":
        return linha["destino"] == linha["rotulo_intencao"]
    if linha["destino"] != "assinatura":
        return False
    if linha["ambigua"]:
        return linha["motivo_capability"] == "baixa_confianca"
    return linha["escolha"] == linha["rotulo_capability"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedores", nargs="+", default=["msd1", "jev", "llm"])
    ap.add_argument("--saida", default="evidencias/avaliacao_capabilities")
    a = ap.parse_args()
    itens = [json.loads(l) for l in (ROOT / "dados/avaliacao_capabilities.jsonl").read_text().splitlines() if l.strip()]
    de_assinatura = [it for it in itens if it["rotulo_intencao"] == "assinatura"]
    led = Ledger(); llm = criar_llm(led); tau = CONFIG["decisao"]["tau"]
    resumo, linhas = {}, []
    for nome in a.provedores:
        clf = ClassificadorIntencao(criar_provedor(nome, led, llm))
        g0 = led.gasto
        lat_int, lat_cap = [], []
        for it in itens:
            t0 = time.perf_counter()
            d = clf.invoke({"mensagens": mensagens(it), "agente_atual": it["agente_atual"], "conversa_id": it["id"]})
            lat_int.append((time.perf_counter() - t0) * 1000)
            destino, motivo = politica_roteamento(d, it["agente_atual"], tau)
            linha = {"provedor": nome, "id": it["id"], "mensagem": it["mensagem"],
                     "rotulo_intencao": it["rotulo_intencao"], "top1_intencao": d.intencao,
                     "confianca_intencao": round(d.confianca, 4), "destino": destino, "motivo_intencao": motivo,
                     "probabilidades_intencao": d.probabilidades}
            if it["rotulo_intencao"] == "assinatura":
                estado = clf.montar_estado({"mensagens": mensagens(it), "agente_atual": it["agente_atual"], "conversa_id": it["id"]})
                t1 = time.perf_counter()
                dc = clf.provedor.decidir(estado, PERGUNTA_CAPABILITY)
                lat_cap.append((time.perf_counter() - t1) * 1000)
                escolha, motivo_cap = politica_capability(dc, estado, tau, it.get("pendente"))
                linha.update({"rotulo_capability": it["rotulo_capability"], "ambigua": it["ambigua"],
                              "top1_capability": dc.intencao, "confianca_capability": round(dc.confianca, 4),
                              "escolha": escolha, "motivo_capability": motivo_cap,
                              "probabilidades_capability": dc.probabilidades, "pendente": it.get("pendente")})
            linhas.append(linha)
        L = [l for l in linhas if l["provedor"] == nome]
        C = [l for l in L if "top1_capability" in l]
        claras = [l for l in C if not l["ambigua"]]
        ok_int = sum(l["destino"] == l["rotulo_intencao"] for l in L)
        ok_top_cap = sum(l["top1_capability"] == l["rotulo_capability"] for l in claras)
        ok_pol_cap = sum((l["motivo_capability"] == "baixa_confianca") if l["ambigua"] else l["escolha"] == l["rotulo_capability"] for l in C)
        por_cap = {c: _taxa(sum(l["top1_capability"] == c for l in claras if l["rotulo_capability"] == c),
                            sum(l["rotulo_capability"] == c for l in claras))
                   for c in REGISTRO}
        resumo[nome] = {
            "n_intencao": len(L), "n_capability": len(C), "n_capability_nao_ambiguas": len(claras),
            "acuracia_intencao": _taxa(sum(l["top1_intencao"] == l["rotulo_intencao"] for l in L), len(L)),
            "acerto_politica_intencao": _taxa(ok_int, len(L)),
            "acuracia_capability_top1": _taxa(ok_top_cap, len(claras)),
            "acerto_politica_capability": _taxa(ok_pol_cap, len(C)),
            "taxa_clarificacao_capability": _taxa(sum(l["motivo_capability"] == "baixa_confianca" for l in C), len(C)),
            "acuracia_por_capability": por_cap,
            "acerto_caminho_completo": _taxa(sum(_caminho_completo(l) for l in L), len(L)),
            "acerto_caminho_completo_assinatura": _taxa(sum(_caminho_completo(l) for l in C), len(C)),
            "latencia_mediana_intencao_ms": round(statistics.median(lat_int)),
            "latencia_mediana_capability_ms": round(statistics.median(lat_cap)) if lat_cap else None,
            "custo_usd": round(led.gasto - g0, 6),
        }
        print(nome, json.dumps(resumo[nome], ensure_ascii=False))
    out = ROOT / a.saida
    out.mkdir(parents=True, exist_ok=True)
    (out / "resumo.json").write_text(json.dumps({
        "tau": tau, "data": time.strftime("%Y-%m-%d %H:%M %z"),
        "n": len(itens), "n_assinatura": len(de_assinatura),
        "definicao_caminho_completo": "destino igual à intenção e, na assinatura, a política da capability acerta o rótulo; nos ambíguos, a capability não executa",
        "provedores": resumo}, indent=2, ensure_ascii=False))
    (out / "predicoes.jsonl").write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in linhas) + "\n")
    print(f"ledger acumulado: US${led.gasto:.4f}")


if __name__ == "__main__":
    main()

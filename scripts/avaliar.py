"""Avaliação de roteamento (secundária): acurácia por provedor no conjunto fictício dados/avaliacao.jsonl.
Uso: python scripts/avaliar.py --provedores msd1 jev llm"""
import argparse, json, pathlib, statistics, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from langchain_core.messages import AIMessage, HumanMessage
from roteador.config import CONFIG
from roteador.decisao import ClassificadorIntencao, criar_provedor
from roteador.grafo import politica_roteamento
from roteador.llm import criar_llm
from roteador.orcamento import Ledger

ROOT = pathlib.Path(__file__).resolve().parents[1]


def mensagens(item):
    ms = [HumanMessage(h["cliente"]) if "cliente" in h else AIMessage(h["atendente"]) for h in item["historico"]]
    return ms + [HumanMessage(item["mensagem"])]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--provedores", nargs="+", default=["msd1", "jev", "llm"])
    a = ap.parse_args()
    itens = [json.loads(l) for l in (ROOT / "dados/avaliacao.jsonl").read_text().splitlines()]
    led = Ledger(); llm = criar_llm(led); tau = CONFIG["decisao"]["tau"]
    resumo, linhas = {}, []
    for nome in a.provedores:
        clf = ClassificadorIntencao(criar_provedor(nome, led, llm)); g0 = led.gasto; lat = []
        for it in itens:
            t0 = time.perf_counter()
            d = clf.invoke({"mensagens": mensagens(it), "agente_atual": it["agente_atual"], "conversa_id": it["id"]})
            lat.append((time.perf_counter() - t0) * 1000)
            destino, motivo = politica_roteamento(d, it["agente_atual"], tau)
            linhas.append({"provedor": nome, "id": it["id"], "rotulo": it["rotulo"], "ambigua": it["ambigua"], "top1": d.intencao,
                           "confianca": round(d.confianca, 4), "destino": destino, "motivo": motivo, "probabilidades": d.probabilidades})
        L = [l for l in linhas if l["provedor"] == nome]
        claras = [l for l in L if not l["ambigua"]]
        aceitas = [l for l in L if l["destino"] != "clarificacao"]
        ok_politica = [l for l in L if l["destino"] == l["rotulo"] or (l["destino"] == "clarificacao" and l["ambigua"])]
        por_classe = {c: round(sum(l["top1"] == c for l in L if l["rotulo"] == c) / max(1, sum(l["rotulo"] == c for l in L)), 3)
                      for c in ["devolucao", "suporte", "financeiro", "fora_de_escopo"]}
        resumo[nome] = {"n": len(L), "acuracia_top1": round(sum(l["top1"] == l["rotulo"] for l in L) / len(L), 3),
                        "acuracia_top1_nao_ambiguas": round(sum(l["top1"] == l["rotulo"] for l in claras) / len(claras), 3),
                        "taxa_clarificacao": round(1 - len(aceitas) / len(L), 3),
                        "acuracia_entre_aceitas": round(sum(l["destino"] == l["rotulo"] for l in aceitas) / max(1, len(aceitas)), 3),
                        "acerto_da_politica": round(len(ok_politica) / len(L), 3),
                        "acuracia_por_classe": por_classe,
                        "latencia_mediana_ms": round(statistics.median(lat)), "custo_usd": round(led.gasto - g0, 6)}
        print(nome, json.dumps(resumo[nome], ensure_ascii=False))
    out = ROOT / "evidencias/avaliacao"; out.mkdir(parents=True, exist_ok=True)
    (out / "resumo.json").write_text(json.dumps({"tau": tau, "data": time.strftime("%Y-%m-%d %H:%M %z"), "provedores": resumo}, indent=2, ensure_ascii=False))
    (out / "predicoes.jsonl").write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in linhas) + "\n")
    print(f"ledger acumulado: US${led.gasto:.4f}")


if __name__ == "__main__":
    main()

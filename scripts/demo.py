"""Demo: conversas livres, em linguagem natural, mostrando o roteamento turno a turno.
Uso: python scripts/demo.py --provedor msd1|jev|llm|msd1+fallback|ab [--simular-queda-msd1]"""
import argparse, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from roteador.decisao import ClassificadorIntencao, criar_provedor, _post_openrouter
from roteador.grafo import construir_grafo, conversar
from roteador.llm import criar_llm
from roteador.orcamento import Ledger

CONVERSAS = {
    "troca_de_assunto": [
        "oi, meu tênis do pedido 10405 ainda não chegou, cadê?",
        "aproveitando, vi que me cobraram duas vezes esse pedido no pix",
        "beleza, e em quanto tempo volta o dinheiro?",
    ],
    "devolucao_natural": [
        "comprei uma camiseta e ficou enorme em mim kkk",
        "é o 10454, chegou faz uns 5 dias",
        "pode sim, quero devolver, ela nem foi usada",
        "valeu! e o reembolso cai como? paguei no cartão",
    ],
    "clarificacao": [
        "não tô satisfeito",
        "o fone do pedido 10418 parou de funcionar, quero trocar",
        "e o fone veio com defeito e ainda fui cobrado de novo no pix, como fica?",
    ],
    "fora_de_escopo_no_meio": [
        "meu pedido 10412 ainda dá tempo de mudar o endereço? mudei de apartamento",
        "rua das flores 123, apto 45, são paulo",
        "aliás, você sabe se vai chover amanhã em SP?",
        "ok rs. então o endereço já ficou certo né?",
    ],
}


def falha_msd1(corpo):
    if corpo["model"].startswith("microsoft/"):
        raise RuntimeError("HTTP 503 no endpoint de decisões (queda simulada)")
    return _post_openrouter(corpo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedor", default="msd1")
    ap.add_argument("--conversas", nargs="*", default=list(CONVERSAS))
    ap.add_argument("--simular-queda-msd1", action="store_true")
    a = ap.parse_args()
    led = Ledger(); llm = criar_llm(led)
    prov = criar_provedor(a.provedor, led, llm, transporte=falha_msd1 if a.simular_queda_msd1 else None)
    app = construir_grafo(ClassificadorIntencao(prov), llm)
    tag = a.provedor.replace("+", "_") + ("_queda" if a.simular_queda_msd1 else "")
    saida = pathlib.Path("evidencias/traces"); saida.mkdir(parents=True, exist_ok=True)
    g0 = led.gasto; registros = []
    for nome in a.conversas:
        cid = f"{nome}-{tag}"
        print(f"\n=== {nome}  (provedor: {prov.nome}) ===")
        for txt in CONVERSAS[nome]:
            t0 = time.perf_counter()
            resp, d = conversar(app, cid, txt)
            probs = " ".join(f"{k}={v:.2f}" for k, v in sorted(d["probabilidades"].items(), key=lambda x: -x[1]))
            extra = (f" fallback: {d['extras']['fallback_motivo']}" if "fallback_motivo" in d["extras"] else "") + \
                    (f" braço A/B: {d['extras']['ab_braco']}" if "ab_braco" in d["extras"] else "")
            print(f"\n👤 {txt}\n   ↳ [{d['provedor']}] {probs} | conf={d['confianca']:.2f} τ={d['tau']} → {d['destino']} ({d['motivo']}){extra}")
            if d["ferramentas"]:
                print("   ↳ ferramentas: " + "; ".join(f"{f['ferramenta']}({json.dumps(f['args'], ensure_ascii=False)})" for f in d["ferramentas"]))
            print(f"🤖 [{d['destino']}] {resp}")
            registros.append({"conversa": nome, "provedor_cfg": a.provedor, "cliente": txt, "resposta": resp,
                              "lat_total_ms": round((time.perf_counter() - t0) * 1000), **{k: d[k] for k in
                              ("provedor", "modelo", "probabilidades", "confianca", "destino", "motivo", "tau", "ferramentas", "custo_usd", "latencia_ms", "extras")}})
    (saida / f"demo_{tag}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n")
    print(f"\nCusto desta execução: US${led.gasto - g0:.5f} | ledger acumulado: US${led.gasto:.4f}")


if __name__ == "__main__":
    main()

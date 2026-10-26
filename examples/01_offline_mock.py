"""Exemplo 1 — roda o grafo inteiro SEM API key (decisão e LLM são dublês; ver roteador/mock.py).
    python examples/01_offline_mock.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from roteador.grafo import conversar
from roteador.mock import montar_app_mock

app = montar_app_mock("msd1")
print("MODO MOCK: heurística de palavras-chave no lugar do MSD1 e LLM falso. Não mede nada.\n")
for fala in ["oi, meu pedido 10405 não chegou, cadê?",
             "aproveitando, me cobraram duas vezes no pix",
             "hmm",
             "vai chover amanhã?"]:
    resposta, d = conversar(app, "exemplo-offline", fala)
    probs = " ".join(f"{k}={v:.2f}" for k, v in sorted(d["probabilidades"].items(), key=lambda x: -x[1]))
    print(f"👤 {fala}\n   ↳ {probs} → {d['destino']} ({d['motivo']})"
          + (f"\n   ↳ ferramentas: {[f['ferramenta'] for f in d['ferramentas']]}" if d["ferramentas"] else ""))
    print(f"🤖 [{d['destino']}] {resposta}\n")

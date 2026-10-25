"""Exemplo 2 — o mínimo com APIs reais (OpenRouter): 2 turnos, ~US$0,001. Requer OPENROUTER_API_KEY.
    python examples/02_live_minimo.py [msd1|jev|llm|msd1+fallback|ab]"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from roteador.decisao import ClassificadorIntencao, criar_provedor
from roteador.grafo import construir_grafo, conversar
from roteador.llm import criar_llm
from roteador.orcamento import Ledger

ledger = Ledger()                                  # teto rígido de custo (config/config.json)
llm = criar_llm(ledger)
app = construir_grafo(ClassificadorIntencao(criar_provedor(sys.argv[1] if len(sys.argv) > 1 else "msd1", ledger, llm)), llm)
for fala in ["comprei uma camiseta e ficou enorme em mim kkk", "é o 10454, chegou faz uns 5 dias"]:
    resposta, d = conversar(app, "exemplo-live", fala)
    print(f"👤 {fala}\n   ↳ [{d['provedor']}] {d['destino']} conf={d['confianca']:.2f} ferramentas={[f['ferramenta'] for f in d['ferramentas']]}\n🤖 {resposta}\n")
print(f"gasto acumulado do ledger: US${ledger.gasto:.4f}")

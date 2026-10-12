"""Chat no terminal. Uso: python scripts/chat.py [--provedor msd1|jev|llm|msd1+fallback|ab]"""
import argparse, pathlib, sys, uuid
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from roteador.decisao import ClassificadorIntencao, criar_provedor
from roteador.grafo import construir_grafo, conversar
from roteador.llm import criar_llm
from roteador.orcamento import Ledger

ap = argparse.ArgumentParser(); ap.add_argument("--provedor", default="msd1"); a = ap.parse_args()
led = Ledger(); llm = criar_llm(led)
app = construir_grafo(ClassificadorIntencao(criar_provedor(a.provedor, led, llm)), llm)
cid = str(uuid.uuid4())
print("LojaExemplo (fictícia) — digite 'sair' para encerrar.")
while (txt := input("\n👤 ").strip()).lower() not in ("sair", "exit"):
    resp, d = conversar(app, cid, txt)
    print(f"   ↳ {d['provedor']}: {d['destino']} ({d['motivo']}, conf={d['confianca']:.2f})")
    print(f"🤖 {resp}")
print(f"gasto acumulado: US${led.gasto:.4f}")

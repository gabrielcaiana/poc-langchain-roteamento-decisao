import sys; sys.path.insert(0, ".")
from roteador.orcamento import Ledger
from roteador.llm import criar_llm
from roteador.decisao import criar_provedor, ClassificadorIntencao
from roteador.grafo import construir_grafo, conversar
led = Ledger(); llm = criar_llm(led)
app = construir_grafo(ClassificadorIntencao(criar_provedor(sys.argv[1] if len(sys.argv)>1 else "msd1", led, llm)), llm)
for t in ["oi, meu tênis do pedido 10405 ainda não chegou, cadê?", "aproveitando, vi que me cobraram duas vezes esse pedido no pix", "beleza, e em quanto tempo volta o dinheiro?"]:
    r, d = conversar(app, "smoke1", t)
    print(">>", t, "\n  ", d["destino"], d["motivo"], {k: round(v, 3) for k, v in d["probabilidades"].items()}, d["ferramentas"], "\n  ", r)
print(led.gasto)

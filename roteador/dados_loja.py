"""Dados 100% fictícios: pedidos, cobranças e política da loja "LojaExemplo".
Ferramentas mock determinísticas. Nada aqui é de cliente real."""
import random

POLITICA = """POLÍTICA LOJAEXEMPLO (fictícia)
- Devolução por arrependimento: até 7 dias corridos após a entrega, produto sem uso, frete de volta grátis.
- Troca/devolução por defeito: até 30 dias (90 dias para eletrônicos com garantia legal); exige foto ou laudo.
- Itens personalizados e de higiene pessoal abertos não podem ser devolvidos por arrependimento.
- Reembolso: cartão = estorno na fatura em até 2 faturas; Pix/boleto = depósito em até 5 dias úteis após recebermos o item.
- Cobrança em duplicidade: estorno da cobrança duplicada em até 7 dias úteis após confirmação.
- Cupom usado em pedido devolvido não é reativado, exceto se o pedido inteiro for devolvido por defeito.
- Reembolso parcial: proporcional ao valor pago pelo item, já descontado o cupom.
- O atendente NÃO pode prometer prazos menores, indenizações ou créditos fora desta política.
"""

STATUS = ["entregue", "em_transito", "processando", "cancelado", "devolucao_em_andamento"]
PAGTO = ["cartao", "pix", "boleto"]
PRODUTOS = [("Fone Bluetooth X1", 199.9, "eletronico"), ("Tênis Corrida Leve", 349.0, "vestuario"),
            ("Liquidificador 900W", 259.9, "eletro"), ("Camiseta Básica", 59.9, "vestuario"),
            ("Notebook 14 Pol", 3299.0, "eletronico"), ("Kit Panelas 5pç", 429.0, "casa"),
            ("Smartwatch Fit", 599.0, "eletronico"), ("Mochila Urbana", 189.0, "acessorio"),
            ("Caneca Personalizada", 49.9, "personalizado"), ("Escova Elétrica", 149.0, "higiene")]


def gerar_pedidos(n=60, seed=7):
    rnd = random.Random(seed)
    pedidos = {}
    for i in range(n):
        pid = str(10400 + i)
        itens = rnd.sample(PRODUTOS, rnd.choice([1, 1, 2, 3]))
        total = round(sum(p[1] for p in itens), 2)
        cupom = rnd.random() < 0.3
        pedidos[pid] = {
            "pedido": pid,
            "status": (st := rnd.choice(STATUS)),
            "dias_desde_entrega": rnd.randint(0, 45) if st in ("entregue", "devolucao_em_andamento") else None,
            "pagamento": rnd.choice(PAGTO),
            "itens": [{"nome": p[0], "preco": p[1], "categoria": p[2]} for p in itens],
            "cupom": "BEMVINDO10" if cupom else None,
            "total_pago": round(total * (0.9 if cupom else 1), 2),
            "cobrancas": 2 if rnd.random() < 0.1 else 1,
        }
    return pedidos


PEDIDOS = gerar_pedidos()


def consultar_pedido(pid: str):
    return PEDIDOS.get(pid)



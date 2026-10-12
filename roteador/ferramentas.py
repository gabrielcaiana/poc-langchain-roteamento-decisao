"""Ferramentas simuladas (dados fictícios). Cada subagente recebe só as que fazem sentido para ele."""
import itertools
from langchain_core.tools import tool
from .dados_loja import POLITICA, consultar_pedido

_protocolo = itertools.count(1)


@tool
def buscar_pedido(numero_pedido: str) -> dict:
    """Consulta um pedido da LojaExemplo pelo número (5 dígitos, ex.: 10412): status, itens, pagamento, valores, dias desde a entrega."""
    return consultar_pedido(numero_pedido.strip()) or {"erro": f"pedido {numero_pedido} não encontrado"}


@tool
def consultar_politica(tema: str) -> str:
    """Retorna a política oficial de pós-venda (devolução, troca, reembolso, cobrança). 'tema' é só para registro."""
    return POLITICA


@tool
def abrir_solicitacao_devolucao(numero_pedido: str, item: str, motivo: str) -> dict:
    """Abre uma solicitação de devolução/troca para um item de um pedido. Só use depois de confirmar elegibilidade e o cliente concordar."""
    p = consultar_pedido(numero_pedido.strip())
    if not p:
        return {"erro": "pedido não encontrado"}
    return {"protocolo": f"DEV-{numero_pedido}-{next(_protocolo):03d}", "item": item, "motivo": motivo,
            "proximo_passo": "etiqueta de postagem enviada por e-mail (simulado)"}


@tool
def abrir_chamado_financeiro(numero_pedido: str, tipo: str, valor: float) -> dict:
    """Abre um chamado financeiro (tipo: 'estorno_duplicidade' | 'reembolso' | 'contestacao') para o pedido e valor informados."""
    return {"protocolo": f"FIN-{numero_pedido}-{next(_protocolo):03d}", "tipo": tipo, "valor": valor,
            "prazo": "conforme política (simulado)"}


@tool
def atualizar_endereco(numero_pedido: str, novo_endereco: str) -> dict:
    """Altera o endereço de entrega de um pedido que ainda está 'processando'.
    Só chame com o endereço completo já informado pelo cliente; nunca com texto provisório."""
    p = consultar_pedido(numero_pedido.strip())
    if not p:
        return {"erro": "pedido não encontrado"}
    if p["status"] != "processando":
        return {"erro": f"não é possível alterar: pedido está '{p['status']}'"}
    return {"ok": True, "novo_endereco": novo_endereco}


FERRAMENTAS = {
    "devolucao": [buscar_pedido, consultar_politica, abrir_solicitacao_devolucao],
    "suporte": [buscar_pedido, atualizar_endereco],
    "financeiro": [buscar_pedido, consultar_politica, abrir_chamado_financeiro],
    "clarificacao": [],
    "fora_de_escopo": [],
}

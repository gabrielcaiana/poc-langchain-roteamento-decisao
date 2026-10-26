"""Modo MOCK (sem API key, custo zero): dublês determinísticos para rodar o grafo inteiro offline.

ATENÇÃO: isto NÃO mede nada sobre o MSD1 nem sobre LLMs. A "decisão" aqui é uma heurística de palavras-chave
e as respostas dos subagentes são montadas a partir do resultado das ferramentas. Serve para ver o fluxo
(handoff, clarificação, memória, ferramentas) funcionando e para os testes de integração."""
from __future__ import annotations

import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

PALAVRAS = {
    "devolucao": ["devol", "troc", "trocar", "defeito", "arrepend", "tamanho", "enorme", "etiqueta"],
    "suporte": ["pedido", "entrega", "chegou", "rastre", "endereço", "endereco", "cancelar", "conta", "cadê", "cade"],
    "financeiro": ["cobra", "reembolso", "estorno", "fatura", "pix", "boleto", "dinheiro", "juros"],
}
FORA = ["chover", "previsão", "time", "receita", "piada", "futebol"]
OPCOES = ["devolucao", "suporte", "financeiro", "fora_de_escopo"]


def transporte_mock(corpo: dict) -> dict:
    """Substitui a chamada HTTP ao endpoint de decisões (mesmo formato de resposta do MSD1/Jev)."""
    msg = corpo["state"]["ultima_mensagem_cliente"].lower()
    placar = {k: sum(p in msg for p in v) for k, v in PALAVRAS.items()}
    placar["fora_de_escopo"] = 3 * sum(p in msg for p in FORA)
    total = sum(placar.values())
    if total == 0:                       # nada reconhecido -> distribuição "indecisa" -> clarificação
        probs = {"devolucao": 0.45, "suporte": 0.30, "financeiro": 0.05, "fora_de_escopo": 0.20}
    else:
        probs = {k: round(0.02 + 0.94 * v / total, 4) for k, v in placar.items()}
        s = sum(probs.values())
        probs = {k: round(v / s, 4) for k, v in probs.items()}
    top = max(probs, key=probs.get)
    return {"model": corpo["model"] + "-mock", "provider": "mock", "usage": {"input_tokens": 0, "cost": 0.0},
            "answers": {"intencao": {"type": "choice", "choice": top, "probabilities": probs, "confidence": probs[top]}}}


class LLMFalso(BaseChatModel):
    """Chat model de mentira com suporte a tool calling: se vê nº de pedido, chama buscar_pedido; depois resume o resultado."""

    tools_nomes: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "llm-falso"

    def bind_tools(self, tools, **kw):
        return self.model_copy(update={"tools_nomes": [getattr(t, "name", str(t)) for t in tools]})

    def _generate(self, messages, stop=None, run_manager=None, **kw) -> ChatResult:
        ultimo = messages[-1]
        sistema = str(messages[0].content) if messages else ""
        if isinstance(ultimo, ToolMessage):
            texto = f"[mock] Consultei o sistema: {str(ultimo.content)[:110]}…"
        else:
            humanas = [m for m in messages if isinstance(m, HumanMessage)]
            fala = str(humanas[-1].content) if humanas else ""
            pedido = re.search(r"\b1\d{4}\b", " ".join(str(m.content) for m in humanas))
            if "buscar_pedido" in self.tools_nomes and pedido:
                msg = AIMessage(content="", tool_calls=[{"name": "buscar_pedido", "args": {"numero_pedido": pedido.group()}, "id": "t1"}])
                return ChatResult(generations=[ChatGeneration(message=msg)])
            if "NÃO responda ao mérito" in sistema:
                texto = "[mock] Pra eu te ajudar direito: é sobre uma troca, sobre o andamento do pedido ou sobre um pagamento?"
            elif "fora do escopo" in sistema:
                texto = "[mock] Essa eu não sei! Eu cuido de pedidos, entregas, trocas e pagamentos da LojaExemplo."
            else:
                texto = f"[mock] Entendi: \"{fala[:60]}\". Me passa o número do pedido pra eu consultar?"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=texto))])


def montar_app_mock(provedor: str = "msd1", tau: float | None = None) -> Any:
    """Grafo completo com provedor de decisão mock + LLM falso + ledger em memória."""
    from .decisao import ClassificadorIntencao, criar_provedor
    from .grafo import construir_grafo
    from .orcamento import LedgerMemoria
    led = LedgerMemoria()
    llm = LLMFalso()
    prov = criar_provedor(provedor if provedor in ("msd1", "jev") else "msd1", led, llm, transporte=transporte_mock)
    return construir_grafo(ClassificadorIntencao(prov), llm, tau=tau)

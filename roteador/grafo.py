"""Orquestração com LangGraph: um nó de decisão (modelo de decisão) e handoff para o subagente da vez.
O grafo NÃO é um roteiro de etapas: a cada mensagem do cliente ele só responde 'quem atende agora?'."""
from __future__ import annotations
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .agentes import PROMPTS, criar_agentes
from .capabilities import atender as atender_capability
from .config import CONFIG
from .decisao import ClassificadorIntencao

ESPECIALISTAS = ("devolucao", "suporte", "financeiro", "assinatura")


class Estado(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]   # memória da conversa (persistida pelo checkpointer)
    agente_atual: str | None                               # quem atendeu o último turno
    decisao: dict                                          # decisão do turno corrente (para trace/UI)
    trilha: Annotated[list[dict], operator.add]            # log de roteamento de todos os turnos
    capability_pendente: str | None                        # capability escolhida que ainda espera um dado


def politica_roteamento(decisao, agente_atual, tau):
    """Converte probabilidades em handoff.
    - confiança >= τ: vai para a intenção mais provável (inclusive fora_de_escopo);
    - confiança < τ mas a mais provável é o especialista que já está atendendo: continua com ele (follow-up);
    - caso contrário: clarificação conversacional."""
    if decisao.confianca >= tau:
        return decisao.intencao, "confiante"
    if agente_atual and decisao.intencao == agente_atual:
        return agente_atual, "continuidade"
    return "clarificacao", "baixa_confianca"


def _so_dialogo(msgs):
    """Visão da conversa para o subagente: só falas do cliente e respostas finais (sem tool calls de colegas)."""
    return [m for m in msgs if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.content and not m.tool_calls)]


def construir_grafo(classificador: ClassificadorIntencao, llm, tau: float | None = None, checkpointer=None):
    tau = CONFIG["decisao"]["tau"] if tau is None else tau
    agentes = criar_agentes(llm)

    def classificar(estado: Estado, config):
        d = classificador.invoke({"mensagens": estado["messages"], "agente_atual": estado.get("agente_atual"),
                                  "conversa_id": config["configurable"]["thread_id"]}, config)
        destino, motivo = politica_roteamento(d, estado.get("agente_atual"), tau)
        info = {**d.dict(), "destino": destino, "motivo": motivo, "tau": tau,
                "mensagem": next(m.content for m in reversed(estado["messages"]) if isinstance(m, HumanMessage))}
        return {"decisao": info, "trilha": [info]}

    def no_agente(nome):
        def rodar(estado: Estado, config):
            sistema = PROMPTS[nome]
            if nome == "clarificacao":
                p = estado["decisao"]["probabilidades"]
                top2 = sorted(p, key=p.get, reverse=True)[:2]
                sistema = sistema.format(candidatos=", ".join(f"{k} ({p[k]:.0%})" for k in top2))
            r = agentes[nome].invoke({"messages": [SystemMessage(sistema)] + _so_dialogo(estado["messages"])}, config)
            novos = r["messages"][len(_so_dialogo(estado["messages"])) + 1:]
            ferramentas = [{"ferramenta": tc["name"], "args": tc["args"]} for m in novos if isinstance(m, AIMessage) for tc in m.tool_calls]
            final = novos[-1]
            final = AIMessage(content=final.content, name=nome)
            trilha_extra = {**estado["decisao"], "ferramentas": ferramentas}
            return {"messages": [final],
                    "agente_atual": nome if nome in ESPECIALISTAS else estado.get("agente_atual"),
                    "capability_pendente": None,
                    "decisao": trilha_extra}
        return rodar

    def no_assinatura(estado: Estado, config):
        base = classificador.montar_estado({"mensagens": estado["messages"], "agente_atual": estado.get("agente_atual"),
                                            "conversa_id": config["configurable"]["thread_id"]})
        r = atender_capability(classificador.provedor, base, tau, estado.get("capability_pendente"))
        return {"messages": [AIMessage(content=r["resposta"], name="assinatura")],
                "agente_atual": "assinatura",
                "capability_pendente": r["pendente"],
                "decisao": {**estado["decisao"], "ferramentas": r["ferramentas"], "capability": r["capability"]}}

    g = StateGraph(Estado)
    g.add_node("classificar", classificar)
    for nome in PROMPTS:
        g.add_node(nome, no_agente(nome))
        g.add_edge(nome, END)
    g.add_node("assinatura", no_assinatura)
    g.add_edge("assinatura", END)
    g.add_edge(START, "classificar")
    destinos = {n: n for n in (*PROMPTS, "assinatura")}
    g.add_conditional_edges("classificar", lambda s: s["decisao"]["destino"], destinos)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def conversar(app, conversa_id: str, texto: str):
    """Um turno: manda a mensagem e devolve (resposta, decisão com ferramentas usadas)."""
    out = app.invoke({"messages": [HumanMessage(texto)]}, {"configurable": {"thread_id": conversa_id}})
    return out["messages"][-1].content, out["decisao"]

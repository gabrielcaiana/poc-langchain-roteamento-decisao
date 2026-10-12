"""Testes 100% offline: transporte HTTP e LLM são substituídos por dublês."""
import itertools
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from roteador.decisao import (ClassificadorIntencao, Decisao, ProvedorAB, ProvedorComFallback,
                              ProvedorOpenRouterDecisao, PERGUNTA)
from roteador.grafo import construir_grafo, conversar, politica_roteamento
from roteador.orcamento import LedgerMemoria, OrcamentoEstourado


def resposta(probs, cost=1e-6, model="microsoft/microsoft-decision-1-x"):
    top = max(probs, key=probs.get)
    return {"model": model, "provider": "mock", "usage": {"input_tokens": 80, "cost": cost},
            "answers": {"intencao": {"type": "choice", "choice": top, "probabilities": probs, "confidence": probs[top]}}}


P = lambda **kw: {"devolucao": 0.0, "suporte": 0.0, "financeiro": 0.0, "fora_de_escopo": 0.0, **kw}


class FakeLLM(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kw):
        return self


def test_provedor_le_probabilidades_registra_custo_e_nao_envia_id():
    enviados, led = [], LedgerMemoria()
    prov = ProvedorOpenRouterDecisao("msd1", "microsoft/microsoft-decision-1", led,
                                     transporte=lambda c: enviados.append(c) or resposta(P(financeiro=0.9, suporte=0.1), cost=3e-6))
    d = prov.decidir({"conversa_id": "abc", "ultima_mensagem_cliente": "cobrança dupla"}, PERGUNTA)
    assert (d.intencao, d.confianca) == ("financeiro", 0.9)
    assert "conversa_id" not in enviados[0]["state"] and enviados[0]["model"] == "microsoft/microsoft-decision-1"
    assert led.gasto == pytest.approx(3e-6)


def test_mesmo_contrato_para_jev():
    prov = ProvedorOpenRouterDecisao("jev", "typesafe/jev-1.13", LedgerMemoria(),
                                     transporte=lambda c: resposta(P(devolucao=1.0), model="typesafe/jev-1.13-x"))
    assert prov.decidir({}, PERGUNTA).intencao == "devolucao"


def test_ledger_bloqueia_antes_de_estourar():
    led = LedgerMemoria(parar_em=1e-9)
    prov = ProvedorOpenRouterDecisao("msd1", "microsoft/microsoft-decision-1", led, transporte=lambda c: 1 / 0)
    with pytest.raises(OrcamentoEstourado):
        prov.decidir({"x": "y"}, PERGUNTA)


def _falha(c):
    raise RuntimeError("HTTP 503")


def test_fallback_usa_secundario_e_registra_motivo():
    led = LedgerMemoria()
    a = ProvedorOpenRouterDecisao("msd1", "m", led, transporte=_falha)
    b = ProvedorOpenRouterDecisao("jev", "j", led, transporte=lambda c: resposta(P(suporte=1.0)))
    d = ProvedorComFallback(a, b).decidir({}, PERGUNTA)
    assert d.provedor == "jev" and "503" in d.extras["fallback_motivo"]


def test_fallback_nao_engole_orcamento():
    class Caro:
        nome = "caro"
        def decidir(self, e, p): raise OrcamentoEstourado("teto")
    with pytest.raises(OrcamentoEstourado):
        ProvedorComFallback(Caro(), Caro()).decidir({}, PERGUNTA)


def test_ab_e_estavel_por_conversa():
    led = LedgerMemoria()
    a = ProvedorOpenRouterDecisao("msd1", "m", led, transporte=lambda c: resposta(P(suporte=1.0)))
    b = ProvedorOpenRouterDecisao("jev", "j", led, transporte=lambda c: resposta(P(suporte=1.0)))
    ab = ProvedorAB(a, b, 0.5)
    bracos = {ab.decidir({"conversa_id": f"c{i}"}, PERGUNTA).provedor for i in range(40)}
    assert bracos == {"msd1", "jev"}
    assert len({ab.decidir({"conversa_id": "c7"}, PERGUNTA).provedor for _ in range(5)}) == 1


@pytest.mark.parametrize("probs,atual,esperado", [
    (P(suporte=0.95, financeiro=0.05), None, ("suporte", "confiante")),
    (P(fora_de_escopo=0.9, suporte=0.1), "suporte", ("fora_de_escopo", "confiante")),
    (P(financeiro=0.6, devolucao=0.4), "financeiro", ("financeiro", "continuidade")),
    (P(financeiro=0.6, devolucao=0.4), "suporte", ("clarificacao", "baixa_confianca")),
    (P(devolucao=0.5, fora_de_escopo=0.5), None, ("clarificacao", "baixa_confianca")),
])
def test_politica_de_roteamento(probs, atual, esperado):
    top = max(probs, key=probs.get)
    assert politica_roteamento(Decisao(top, probs, probs[top], "t", "t"), atual, 0.75) == esperado


def test_classificador_monta_estado_com_historico():
    clf = ClassificadorIntencao(None, historico_turnos=2)
    est = clf.montar_estado({"mensagens": [HumanMessage("a"), AIMessage("b"), HumanMessage("c"), AIMessage("d"), HumanMessage("e?")],
                             "agente_atual": "suporte", "conversa_id": "x"})
    assert est["ultima_mensagem_cliente"] == "e?" and est["especialista_atual"] == "suporte"
    assert est["historico"] == [{"cliente": "c"}, {"atendente": "d"}]


def test_grafo_multiturno_handoff_clarificacao_e_memoria():
    sequencia = iter([P(suporte=0.99), P(financeiro=0.98), P(financeiro=0.55, devolucao=0.45),
                      P(devolucao=0.5, suporte=0.5), P(fora_de_escopo=0.97)])
    vistos = []
    led = LedgerMemoria()
    prov = ProvedorOpenRouterDecisao("msd1", "m", led,
                                     transporte=lambda c: vistos.append(c["state"]) or resposta(next(sequencia)))
    llm = FakeLLM(responses=[AIMessage(content=f"resposta {i}") for i in range(10)])
    app = construir_grafo(ClassificadorIntencao(prov), llm, tau=0.75)
    destinos = [conversar(app, "conv1", t)[1]["destino"] for t in
                ["cadê meu pedido?", "e me cobraram 2x", "quanto tempo?", "hmm", "vai chover?"]]
    assert destinos == ["suporte", "financeiro", "financeiro", "clarificacao", "fora_de_escopo"]
    # memória: o 5º turno enxerga o histórico e quem estava atendendo
    assert vistos[-1]["especialista_atual"] == "financeiro"
    assert {"cliente": "e me cobraram 2x"} in vistos[-1]["historico"] and len(vistos[-1]["historico"]) == 6  # janela de 6
    estado = app.get_state({"configurable": {"thread_id": "conv1"}}).values
    assert [m.name for m in estado["messages"] if isinstance(m, AIMessage)] == destinos
    assert len(estado["trilha"]) == 5

"""Capabilities de assinatura, offline: o modelo de decisão é um dublê e nada chama a API."""
import json
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from roteador.assinaturas import ASSINATURAS, resetar
from roteador.capabilities import PERGUNTA as PERGUNTA_CAPABILITY, REGISTRO, atender
from roteador.config import ROOT
from roteador.decisao import INTENCOES, PERGUNTA, ClassificadorIntencao, ProvedorOpenRouterDecisao
from roteador.grafo import construir_grafo, conversar
from roteador.orcamento import LedgerMemoria


@pytest.fixture(autouse=True)
def _base_limpa():
    resetar()
    yield
    resetar()


def resp(probs, cost=0.0):
    top = max(probs, key=probs.get)
    return {"model": "mock", "provider": "mock", "usage": {"cost": cost},
            "answers": {"intencao": {"probabilities": probs, "confidence": probs[top]}}}


def provedor(probs):
    return ProvedorOpenRouterDecisao("msd1", "m", LedgerMemoria(), transporte=lambda c: resp(probs))


def est(texto, historico=None):
    return {"conversa_id": "t", "especialista_atual": "assinatura", "historico": historico or [],
            "ultima_mensagem_cliente": texto}


class FakeLLM(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kw):
        return self


def test_conjunto_de_avaliacao_tem_rotulos_validos():
    linhas = [json.loads(l) for l in (ROOT / "dados/avaliacao_capabilities.jsonl").read_text().splitlines() if l.strip()]
    assert len(linhas) == 27 and len({l["id"] for l in linhas}) == 27
    for l in linhas:
        assert l["rotulo_intencao"] in INTENCOES
        if l["rotulo_capability"]:
            assert l["rotulo_capability"] in REGISTRO and not l["ambigua"]
        if l["ambigua"]:
            assert l["rotulo_intencao"] == "assinatura" and l["rotulo_capability"] is None
        if l["pendente"]:
            assert l["pendente"] in REGISTRO


def test_assinatura_e_capability_sao_perguntas_diferentes():
    assert "assinatura" in PERGUNTA["criteria"]
    assert "cancelar_assinatura" in PERGUNTA_CAPABILITY["criteria"]
    assert "devolucao" not in PERGUNTA_CAPABILITY["criteria"]
    assert "assinatura" not in PERGUNTA_CAPABILITY["criteria"]


def test_cancelar_executa_e_a_consulta_ve_o_efeito():
    r = atender(provedor({"cancelar_assinatura": 0.97, "consultar_assinatura": 0.03}),
                est("cancela a assinatura 50021"), 0.75, None)
    assert r["capability"]["executada"] and r["capability"]["nome"] == "cancelar_assinatura"
    assert ASSINATURAS["50021"]["status"] == "cancelada"
    assert "Cancelei" in r["resposta"] and "50021" in r["resposta"]
    consulta = atender(provedor({"consultar_assinatura": 0.99}), est("como está a 50021?"), 0.75, None)
    assert "cancelada" in consulta["resposta"]


def test_confianca_baixa_nao_executa():
    r = atender(provedor({"cancelar_assinatura": 0.55, "pausar_assinatura": 0.45}),
                est("tanto faz a 50021"), 0.75, None)
    assert r["capability"]["executada"] is False and r["capability"]["motivo"] == "baixa_confianca"
    assert ASSINATURAS["50021"]["status"] == "ativa"
    assert "cancelar" in r["resposta"] and "pausar" in r["resposta"]


def test_sem_numero_pede_e_deixa_pendente():
    r = atender(provedor({"cancelar_assinatura": 0.96}), est("quero cancelar minha assinatura"), 0.75, None)
    assert r["capability"]["executada"] is False
    assert r["capability"]["faltando"] == ["numero_assinatura"]
    assert r["pendente"] == "cancelar_assinatura"
    assert ASSINATURAS["50021"]["status"] == "ativa"
    assert "número da assinatura" in r["resposta"]


def test_numero_de_pedido_nao_vale_como_assinatura():
    r = atender(provedor({"cancelar_assinatura": 0.98}), est("cancela o pedido 10405"), 0.75, None)
    assert r["capability"]["faltando"] == ["numero_assinatura"]
    assert r["capability"]["executada"] is False


def test_pendente_com_so_o_numero_cancela_mesmo_com_confianca_baixa():
    primeiro = atender(provedor({"cancelar_assinatura": 0.96}), est("quero cancelar minha assinatura"), 0.75, None)
    segundo = atender(provedor({"consultar_assinatura": 0.42, "cancelar_assinatura": 0.40, "pausar_assinatura": 0.18}),
                      est("50021", [{"cliente": "quero cancelar minha assinatura"}]), 0.75, primeiro["pendente"])
    assert segundo["capability"]["motivo"] == "pendente" and segundo["capability"]["executada"]
    assert ASSINATURAS["50021"]["status"] == "cancelada"


def test_confianca_alta_troca_a_capability_pendente():
    r = atender(provedor({"pausar_assinatura": 0.96, "cancelar_assinatura": 0.04}),
                est("na verdade pausa a 50021"), 0.75, "cancelar_assinatura")
    assert r["capability"]["nome"] == "pausar_assinatura" and r["capability"]["motivo"] == "confiante"
    assert ASSINATURAS["50021"]["status"] == "pausada"


@pytest.mark.parametrize("texto,escolha,esperado", [
    ("quero trocar o produto da assinatura 50021 para shampoo", "trocar_produto",
     lambda: ASSINATURAS["50021"]["produto"] == "shampoo"),
    ("quero assinar outro produto, o shampoo, mantendo a 50021", "incluir_assinatura",
     lambda: ASSINATURAS["50026"]["produto"] == "shampoo" and ASSINATURAS["50021"]["produto"] == "cafe_graos"),
    ("pula a próxima entrega da 50025", "pular_proxima_entrega",
     lambda: ASSINATURAS["50025"]["proxima_entrega"] == "2026-11-03"),
    ("muda a 50022 para mensal", "alterar_frequencia",
     lambda: ASSINATURAS["50022"]["frequencia"] == "mensal" and ASSINATURAS["50022"]["proxima_entrega"] == "2026-10-28"),
    ("pausa a 50021 por 1 mês", "pausar_assinatura",
     lambda: ASSINATURAS["50021"]["status"] == "pausada" and ASSINATURAS["50021"]["proxima_entrega"] == "2026-12-03"),
    ("retoma a assinatura 50023", "retomar_assinatura",
     lambda: ASSINATURAS["50023"]["status"] == "ativa"),
    ("muda o endereço da assinatura 50022 para Rua Nova, 10, Recife", "alterar_endereco_entrega",
     lambda: ASSINATURAS["50022"]["endereco"] == "Rua Nova, 10, Recife"),
])
def test_capabilities_de_recorrencia(texto, escolha, esperado):
    r = atender(provedor({escolha: 0.98}), est(texto), 0.75, None)
    assert r["capability"]["nome"] == escolha and r["capability"]["executada"]
    assert esperado()
    assert "erro" not in r["capability"]["resultado"]


def test_regras_recusam_sem_efeito_indevido():
    recusas = [
        ("cancela a 50024", "cancelar_assinatura", "50024", "cancelada"),
        ("pula a entrega da 50023", "pular_proxima_entrega", "50023", "pausada"),
        ("troca a 50021 para café em grãos", "trocar_produto", "50021", "ativa"),
        ("retoma a 50021", "retomar_assinatura", "50021", "ativa"),
    ]
    for texto, escolha, numero, status in recusas:
        resetar()
        r = atender(provedor({escolha: 0.99}), est(texto), 0.75, None)
        assert r["capability"]["executada"]
        assert "erro" in r["capability"]["resultado"]
        assert ASSINATURAS[numero]["status"] == status
        assert r["resposta"] == r["capability"]["resultado"]["erro"]


def _grafo(transporte):
    prov = ProvedorOpenRouterDecisao("msd1", "m", LedgerMemoria(), transporte=transporte)
    llm = FakeLLM(responses=[AIMessage(content=f"resposta {i}") for i in range(6)])
    return construir_grafo(ClassificadorIntencao(prov), llm, tau=0.75)


def _resp_por_pergunta(corpo, intencoes, caps):
    crit = corpo["questions"]["intencao"]["criteria"]
    if "cancelar_assinatura" in crit:
        return resp(next(caps))
    return resp(next(intencoes))


def test_grafo_pede_o_numero_e_outro_assunto_nao_cancela():
    intencoes = iter([{"assinatura": 0.99, "suporte": 0.01}, {"suporte": 0.99, "assinatura": 0.01}])
    caps = iter([{"cancelar_assinatura": 0.95}])
    app = _grafo(lambda c: _resp_por_pergunta(c, intencoes, caps))
    texto, d = conversar(app, "cap-1", "quero cancelar minha assinatura")
    assert d["destino"] == "assinatura" and d["capability"]["nome"] == "cancelar_assinatura"
    assert d["capability"]["executada"] is False and "número da assinatura" in texto
    assert app.get_state({"configurable": {"thread_id": "cap-1"}}).values["capability_pendente"] == "cancelar_assinatura"
    texto, d = conversar(app, "cap-1", "cadê o pedido 10405?")
    assert d["destino"] == "suporte" and "capability" not in d
    assert ASSINATURAS["50021"]["status"] == "ativa"
    assert app.get_state({"configurable": {"thread_id": "cap-1"}}).values["capability_pendente"] is None


def test_grafo_dois_turnos_completa_o_cancelamento():
    intencoes = iter([{"assinatura": 0.99}, {"assinatura": 0.9}])
    caps = iter([{"cancelar_assinatura": 0.96},
                 {"consultar_assinatura": 0.42, "cancelar_assinatura": 0.40, "pausar_assinatura": 0.18}])
    app = _grafo(lambda c: _resp_por_pergunta(c, intencoes, caps))
    conversar(app, "cap-2", "quero cancelar minha assinatura")
    texto, d = conversar(app, "cap-2", "50021")
    assert d["destino"] == "assinatura"
    assert d["capability"]["motivo"] == "pendente" and d["capability"]["executada"]
    assert d["ferramentas"][0]["ferramenta"] == "cancelar_assinatura"
    assert "Cancelei" in texto and ASSINATURAS["50021"]["status"] == "cancelada"
    assert app.get_state({"configurable": {"thread_id": "cap-2"}}).values["capability_pendente"] is None

"""Camada de decisão: provedores intercambiáveis (MSD1, Jev, classificador LLM) atrás de uma interface única,
e o classificador de intenção exposto como Runnable do LangChain."""
from __future__ import annotations
import hashlib, json, os, time, urllib.error, urllib.request
from dataclasses import dataclass, field, asdict
from typing import Callable, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableConfig

from .config import CONFIG, PRECOS
from .orcamento import Ledger

URL_DECISOES = "https://openrouter.ai/api/alpha/decisions"

INTENCOES = {
    "devolucao": "Devolução, troca, arrependimento, produto com defeito ou errado que o cliente quer devolver/trocar, etiqueta e coleta.",
    "suporte": "Status e rastreio de pedido avulso, entrega, atraso, extravio, endereço de um pedido, cancelamento antes do envio, conta/cadastro, uso de produto. Não é assinatura recorrente.",
    "financeiro": "Reembolso, cobrança duplicada/indevida, juros, boleto, estorno no cartão ou Pix, valores pagos e devolvidos.",
    "assinatura": "Assinatura recorrente: cancelar, pausar, retomar, pular a próxima entrega, mudar frequência, trocar o produto, assinar outro produto ou mudar o endereço das próximas entregas.",
    "fora_de_escopo": "Assunto sem relação com pedidos, assinaturas, produtos ou pagamentos da loja.",
}
PERGUNTA = {"type": "choice",
            "instructions": ("Num atendimento de pós-venda, qual especialista deve responder à ÚLTIMA mensagem do cliente? "
                             "Use o histórico para entender mensagens curtas de continuação (ex.: 'e quanto tempo demora?')."),
            "criteria": INTENCOES}


@dataclass
class Decisao:
    intencao: str
    probabilidades: dict
    confianca: float
    provedor: str
    modelo: str
    custo_usd: float = 0.0
    latencia_ms: float = 0.0
    extras: dict = field(default_factory=dict)

    def dict(self):
        return asdict(self)


class ProvedorDecisao(Protocol):
    nome: str
    def decidir(self, estado: dict, pergunta: dict) -> Decisao: ...


def _post_openrouter(corpo: dict, timeout=30) -> dict:
    req = urllib.request.Request(URL_DECISOES, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                                          "Content-Type": "application/json", "X-Title": "poc-langchain-roteamento-decisao"})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and tentativa < 2:
                time.sleep(2 ** tentativa); continue
            raise RuntimeError(f"HTTP {e.code} no endpoint de decisões: {e.read()[:200]!r}") from None


class ProvedorOpenRouterDecisao:
    """Qualquer modelo do endpoint /api/alpha/decisions (MSD1, Jev...). Mesmo contrato: model + state + questions."""

    def __init__(self, nome: str, modelo: str, ledger: Ledger, transporte: Callable[[dict], dict] = _post_openrouter):
        self.nome, self.modelo, self.ledger, self.transporte = nome, modelo, ledger, transporte

    def decidir(self, estado, pergunta):
        tokens_est = len(json.dumps([estado, pergunta], ensure_ascii=False)) // 2 + 600  # conservador
        self.ledger.reservar(tokens_est * max(PRECOS.get(self.modelo, {}).get("in", 1e-7), 1e-7) * 3)
        t0 = time.perf_counter()
        estado = {k: v for k, v in estado.items() if k != "conversa_id"}  # id só serve ao A/B
        r = self.transporte({"model": self.modelo, "state": estado, "questions": {"intencao": pergunta}})
        lat = (time.perf_counter() - t0) * 1000
        custo = float(r.get("usage", {}).get("cost") or 0.0)
        self.ledger.registrar(self.modelo, custo)
        a = r["answers"]["intencao"]
        probs = {k: round(float(v), 6) for k, v in a["probabilities"].items()}
        top = max(probs, key=probs.get)
        return Decisao(top, probs, probs[top], self.nome, r.get("model", self.modelo), custo, lat,
                       {"usage": r.get("usage", {}), "provedor_infra": r.get("provider")})


class ProvedorClassificadorLLM:
    """Plano B: um LLM gerativo com saída estruturada devolvendo uma nota 0-1 por opção.
    O schema sai da pergunta recebida, então a mesma classe classifica intenção ou capability.
    Não é calibrado como um modelo de decisão; serve como fallback quando o endpoint alpha falha."""

    def __init__(self, llm, nome="llm"):
        self.nome, self.llm = nome, llm

    def decidir(self, estado, pergunta):
        opcoes = list(pergunta["criteria"])
        schema = {"title": "Classificacao", "type": "object",
                  "properties": {k: {"type": "number", "description": f"probabilidade 0-1: {v}"} for k, v in pergunta["criteria"].items()},
                  "required": opcoes}
        chain = self.llm.with_structured_output(schema, method="json_schema")
        t0 = time.perf_counter()
        prompt = (f"{pergunta['instructions']}\nOpções: {json.dumps(pergunta['criteria'], ensure_ascii=False)}\n"
                  f"Estado da conversa: {json.dumps(estado, ensure_ascii=False)}\n"
                  "Devolva uma probabilidade por opção (somando 1).")
        bruto = chain.invoke(prompt)
        s = sum(max(float(bruto.get(k, 0)), 0) for k in opcoes) or 1.0
        probs = {k: round(max(float(bruto.get(k, 0)), 0) / s, 6) for k in opcoes}
        top = max(probs, key=probs.get)
        return Decisao(top, probs, probs[top], self.nome, getattr(self.llm, "model_name", "llm"), 0.0,
                       (time.perf_counter() - t0) * 1000, {"custo_no_ledger_via_callback": True})


class ProvedorComFallback:
    """Tenta o primário; se der erro (HTTP, timeout, schema), cai para o secundário e registra o motivo."""

    def __init__(self, primario, secundario):
        self.primario, self.secundario = primario, secundario
        self.nome = f"{primario.nome}>{secundario.nome}"

    def decidir(self, estado, pergunta):
        try:
            return self.primario.decidir(estado, pergunta)
        except Exception as e:  # noqa: BLE001 - qualquer falha do primário aciona o plano B
            if e.__class__.__name__ == "OrcamentoEstourado":
                raise
            d = self.secundario.decidir(estado, pergunta)
            d.extras["fallback_motivo"] = f"{type(e).__name__}: {str(e)[:120]}"
            return d


class ProvedorAB:
    """Teste A/B estável por conversa: o hash do thread_id decide o braço, então a conversa inteira usa o mesmo provedor."""

    def __init__(self, a, b, proporcao_b=0.5):
        self.a, self.b, self.proporcao_b = a, b, proporcao_b
        self.nome = f"ab({a.nome}|{b.nome})"

    def braco(self, conversa_id: str):
        h = int(hashlib.sha256(conversa_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return self.b if h < self.proporcao_b else self.a

    def decidir(self, estado, pergunta):
        d = self.braco(estado.get("conversa_id", "")).decidir(estado, pergunta)
        d.extras["ab_braco"] = d.provedor
        return d


def criar_provedor(nome: str, ledger: Ledger, llm=None, transporte=None):
    """Fábrica guiada pela flag de config (decisao.provedor)."""
    m = CONFIG["decisao"]["modelos"]
    kw = {"transporte": transporte} if transporte else {}
    msd1 = lambda: ProvedorOpenRouterDecisao("msd1", m["msd1"], ledger, **kw)
    jev = lambda: ProvedorOpenRouterDecisao("jev", m["jev"], ledger, **kw)
    if nome == "msd1": return msd1()
    if nome == "jev": return jev()
    if nome == "llm": return ProvedorClassificadorLLM(llm)
    if nome == "msd1+fallback": return ProvedorComFallback(msd1(), ProvedorComFallback(jev(), ProvedorClassificadorLLM(llm)))
    if nome == "ab": return ProvedorAB(msd1(), jev(), CONFIG["decisao"]["ab_proporcao_jev"])
    raise ValueError(f"provedor desconhecido: {nome}")


def _historico_compacto(mensagens: list[BaseMessage], n: int):
    out = []
    for m in mensagens:
        if isinstance(m, HumanMessage):
            out.append({"cliente": m.content})
        elif isinstance(m, AIMessage) and m.content and not m.tool_calls:
            out.append({"atendente": str(m.content)[:300]})
    return out[-n:]


class ClassificadorIntencao(Runnable):
    """Runnable do LangChain: recebe {mensagens, agente_atual, conversa_id} e devolve uma Decisao.
    Por ser Runnable, aparece nos traces, aceita config/callbacks e compõe com | como qualquer outro componente."""

    def __init__(self, provedor: ProvedorDecisao, historico_turnos: int | None = None):
        self.provedor = provedor
        self.n = historico_turnos or CONFIG["decisao"]["historico_turnos"]

    def montar_estado(self, entrada: dict) -> dict:
        msgs = entrada["mensagens"]
        ultima = next(m.content for m in reversed(msgs) if isinstance(m, HumanMessage))
        return {"conversa_id": entrada.get("conversa_id", ""),
                "especialista_atual": entrada.get("agente_atual") or "nenhum",
                "historico": _historico_compacto(msgs[:-1], self.n),
                "ultima_mensagem_cliente": ultima}

    def invoke(self, input: dict, config: RunnableConfig | None = None, **kwargs) -> Decisao:
        return self.provedor.decidir(self.montar_estado(input), PERGUNTA)

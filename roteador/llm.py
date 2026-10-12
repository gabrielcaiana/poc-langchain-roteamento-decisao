"""Modelo gerativo dos subagentes (via OpenRouter, API compatível com OpenAI) + callback que alimenta o ledger."""
import os
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from .config import CONFIG, PRECOS
from .orcamento import Ledger


class CallbackCusto(BaseCallbackHandler):
    """Reserva antes de cada chamada e registra o custo real (usage.cost do OpenRouter) depois."""

    def __init__(self, ledger: Ledger, modelo: str, max_tokens: int):
        self.ledger, self.modelo, self.max_tokens = ledger, modelo, max_tokens

    def on_chat_model_start(self, serialized, messages, **kw):
        chars = sum(len(str(m.content)) for lote in messages for m in lote)
        p = PRECOS[self.modelo]
        self.ledger.reservar((chars // 2 + 1500) * p["in"] + self.max_tokens * p["out"])

    def on_llm_end(self, response, **kw):
        u = (response.llm_output or {}).get("token_usage") or {}
        custo = u.get("cost")
        if custo is None:
            p = PRECOS[self.modelo]
            custo = u.get("prompt_tokens", 0) * p["in"] + u.get("completion_tokens", 0) * p["out"]
        self.ledger.registrar(self.modelo, float(custo))


def criar_llm(ledger: Ledger, **kw):
    g = CONFIG["geracao"]
    return ChatOpenAI(model=g["modelo"], base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"],
                      max_tokens=g["max_tokens"], temperature=g["temperatura"], timeout=60, max_retries=2,
                      extra_body={"usage": {"include": True}},
                      default_headers={"X-Title": "poc-langchain-roteamento-decisao"},
                      callbacks=[CallbackCusto(ledger, g["modelo"], g["max_tokens"])], **kw)

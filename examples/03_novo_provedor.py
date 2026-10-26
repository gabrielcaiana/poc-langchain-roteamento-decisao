"""Exemplo 3 — plugar um provedor de decisão novo em ~15 linhas (offline).
Qualquer objeto com `nome` e `decidir(estado, pergunta) -> Decisao` serve; o resto do grafo não muda.
    python examples/03_novo_provedor.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from roteador.decisao import ClassificadorIntencao, Decisao, ProvedorComFallback
from roteador.grafo import construir_grafo, conversar
from roteador.mock import LLMFalso


class ProvedorRegras:
    """Provedor fictício baseado em regra: manda tudo que cita 'cobrança' para o financeiro."""
    nome = "regras"

    def decidir(self, estado, pergunta):
        financeiro = "cobra" in estado["ultima_mensagem_cliente"].lower()
        probs = {"devolucao": 0.0, "suporte": 0.0, "financeiro": 1.0 if financeiro else 0.0, "fora_de_escopo": 0.0 if financeiro else 1.0}
        top = max(probs, key=probs.get)
        return Decisao(top, probs, probs[top], self.nome, "regras-v0")


class ProvedorQueFalha:
    nome = "instavel"

    def decidir(self, estado, pergunta):
        raise RuntimeError("HTTP 503 (simulado)")


llm = LLMFalso()
# o fallback é só composição: tenta o primeiro, cai pro segundo
app = construir_grafo(ClassificadorIntencao(ProvedorComFallback(ProvedorQueFalha(), ProvedorRegras())), llm)
resposta, d = conversar(app, "ex3", "fui cobrado duas vezes")
print(d["provedor"], "→", d["destino"], "| motivo do fallback:", d["extras"]["fallback_motivo"])

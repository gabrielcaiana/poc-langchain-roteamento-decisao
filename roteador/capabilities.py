"""Capabilities de assinatura recorrente.

Uma capability é uma habilidade declarada (nome, descrição, função). Ela não conversa
e não escolhe ferramenta. O mesmo provedor de decisão que roteia especialistas responde
uma segunda pergunta: qual capability executa esta mensagem. O código executa.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Callable

from . import assinaturas as loja

ID_RE = re.compile(r"\b(50\d{3})\b")
FREQ_RE = re.compile(r"\b(semanal|quinzenal|mensal)\b", re.I)
CICLO_RE = re.compile(r"\b(\d+)\s*(mês|mes|meses|ciclo|ciclos)\b", re.I)
ENDERECO_RE = re.compile(r"\bpara\s+(.{8,})$", re.I | re.S)

ROTULOS = {
    "consultar_assinatura": "consultar a assinatura",
    "cancelar_assinatura": "cancelar",
    "pausar_assinatura": "pausar",
    "retomar_assinatura": "retomar",
    "pular_proxima_entrega": "pular a próxima entrega",
    "alterar_frequencia": "mudar a frequência",
    "alterar_endereco_entrega": "mudar o endereço das próximas entregas",
    "trocar_produto": "trocar o produto",
    "incluir_assinatura": "assinar outro produto",
}
SINAIS = {
    "cancelar_assinatura": ("cancel",),
    "pausar_assinatura": ("paus",),
    "retomar_assinatura": ("retom", "reativ"),
    "pular_proxima_entrega": ("pul",),
    "alterar_frequencia": ("semanal", "quinzenal", "mensal", "frequenc", "frequênc"),
    "alterar_endereco_entrega": ("enderec", "endereç"),
    "trocar_produto": ("troc", "em vez", "no lugar"),
    "incluir_assinatura": ("assinar outro", "outra assinatura", "incluir"),
    "consultar_assinatura": ("quando chega", "qual produto", "status"),
}
PERGUNTAS_FALTA = {
    "numero_assinatura": "me passa o número da assinatura",
    "produto": "qual produto você quer (" + ", ".join(loja.PRODUTOS.values()) + ")",
    "frequencia": "qual frequência: semanal, quinzenal ou mensal",
    "endereco": "qual é o endereço completo das próximas entregas",
}


@dataclass(frozen=True)
class Capability:
    nome: str
    descricao: str
    executar: Callable[[dict], dict]
    exige: tuple[str, ...]


REGISTRO: dict[str, Capability] = {
    c.nome: c for c in (
        Capability("consultar_assinatura",
                   "Saber status, produto, frequência, próxima entrega ou endereço. Não muda nada.",
                   loja.consultar, ("numero_assinatura",)),
        Capability("cancelar_assinatura",
                   "Encerrar a assinatura de vez. Sem próximas entregas.",
                   loja.cancelar, ("numero_assinatura",)),
        Capability("pausar_assinatura",
                   "Suspender por um tempo, sem cancelar.",
                   loja.pausar, ("numero_assinatura",)),
        Capability("retomar_assinatura",
                   "Reativar uma assinatura pausada.",
                   loja.retomar, ("numero_assinatura",)),
        Capability("pular_proxima_entrega",
                   "Manter a assinatura e adiar só a próxima entrega.",
                   loja.pular, ("numero_assinatura",)),
        Capability("alterar_frequencia",
                   "Mudar o ritmo para semanal, quinzenal ou mensal.",
                   loja.alterar_frequencia, ("numero_assinatura", "frequencia")),
        Capability("alterar_endereco_entrega",
                   "Mudar o endereço das próximas entregas da recorrência, não de um pedido avulso.",
                   loja.alterar_endereco, ("numero_assinatura", "endereco")),
        Capability("trocar_produto",
                   "Substituir o produto desta assinatura por outro do catálogo recorrente.",
                   loja.trocar_produto, ("numero_assinatura", "produto")),
        Capability("incluir_assinatura",
                   "Criar outra assinatura, de outro produto, sem cancelar a atual.",
                   loja.incluir, ("numero_assinatura", "produto")),
    )
}

PERGUNTA = {
    "type": "choice",
    "instructions": ("A conversa já está na assinatura recorrente. Qual capability executa a ÚLTIMA mensagem? "
                     "Use o histórico quando a mensagem só completa um pedido anterior, por exemplo só o número."),
    "criteria": {c.nome: c.descricao for c in REGISTRO.values()},
}


def textos_cliente(estado: dict) -> str:
    partes = [estado.get("ultima_mensagem_cliente") or ""]
    for item in estado.get("historico") or []:
        if "cliente" in item:
            partes.append(item["cliente"])
    return "\n".join(partes)


def _id(blob: str) -> str | None:
    achados = ID_RE.findall(blob)
    return achados[-1] if achados else None


def _frequencia(blob: str) -> str | None:
    m = FREQ_RE.search(blob)
    return m.group(1).lower() if m else None


def _ciclos(texto: str) -> int | None:
    m = CICLO_RE.search(texto)
    return int(m.group(1)) if m else None


def _endereco(texto: str) -> str | None:
    m = ENDERECO_RE.search(texto.strip())
    return m.group(1).strip(" .") if m else None


def montar_args(nome: str, blob: str, ultima: str) -> tuple[dict, list[str]]:
    cap = REGISTRO[nome]
    args, faltando = {}, []
    if "numero_assinatura" in cap.exige:
        numero = _id(blob)
        if numero:
            args["numero"] = numero
        else:
            faltando.append("numero_assinatura")
    if "produto" in cap.exige:
        produto = loja.achar_produto(blob)
        if produto:
            args["produto"] = produto
        else:
            faltando.append("produto")
    if "frequencia" in cap.exige:
        frequencia = _frequencia(blob)
        if frequencia:
            args["frequencia"] = frequencia
        else:
            faltando.append("frequencia")
    if "endereco" in cap.exige:
        endereco = _endereco(ultima)
        if endereco:
            args["endereco"] = endereco
        else:
            faltando.append("endereco")
    if nome == "pausar_assinatura":
        args["ciclos"] = _ciclos(ultima) or 1
    if nome == "incluir_assinatura":
        frequencia = _frequencia(blob)
        if frequencia:
            args["frequencia"] = frequencia
    return args, faltando


def _sinais_de_outra(pendente: str, texto: str) -> bool:
    t = texto.lower()
    return any(nome != pendente and any(s in t for s in chaves) for nome, chaves in SINAIS.items())


def _so_preenche(pendente: str, blob: str, ultima: str) -> bool:
    if pendente not in REGISTRO or _sinais_de_outra(pendente, ultima):
        return False
    _, faltando = montar_args(pendente, blob, ultima)
    return not faltando


def _pacote(nome, motivo, decisao, executada, faltando=None, ferramentas=None, pendente=None):
    return {"pendente": pendente, "ferramentas": ferramentas or [],
            "capability": {"nome": nome, "motivo": motivo, "confianca": decisao.confianca,
                           "probabilidades": decisao.probabilidades, "executada": executada,
                           "faltando": faltando or []}}


def falar(nome: str, resultado: dict) -> str:
    if "erro" in resultado:
        return resultado["erro"]
    n = resultado.get("numero")
    if nome == "consultar_assinatura":
        return (f"A assinatura {n} está {resultado['status']}: {resultado['produto_nome']}, "
                f"entrega {resultado['frequencia']}, próxima em {resultado['proxima_txt']}, "
                f"no endereço {resultado['endereco']}.")
    if nome == "cancelar_assinatura":
        return (f"Cancelei a assinatura {n} ({resultado['produto_nome']}). "
                f"Protocolo {resultado['protocolo']}. Não há próxima entrega.")
    if nome == "pausar_assinatura":
        return (f"Pausei a assinatura {n} por {resultado['ciclos']} ciclo(s). "
                f"Protocolo {resultado['protocolo']}. A próxima entrega fica para {resultado['proxima_txt']}.")
    if nome == "retomar_assinatura":
        return (f"Retomei a assinatura {n} ({resultado['produto_nome']}). "
                f"Protocolo {resultado['protocolo']}. Próxima entrega em {resultado['proxima_txt']}.")
    if nome == "pular_proxima_entrega":
        return (f"Pulei a próxima entrega da assinatura {n}. Protocolo {resultado['protocolo']}. "
                f"A seguinte fica para {resultado['proxima_txt']}.")
    if nome == "alterar_frequencia":
        return (f"A assinatura {n} agora é {resultado['frequencia']}. Protocolo {resultado['protocolo']}. "
                f"A próxima entrega continua em {resultado['proxima_txt']}.")
    if nome == "alterar_endereco_entrega":
        return (f"Atualizei o endereço da assinatura {n} para {resultado['endereco']}. "
                f"Protocolo {resultado['protocolo']}. Vale para as próximas entregas.")
    if nome == "trocar_produto":
        return (f"Troquei o produto da assinatura {n} para {resultado['produto_nome']}. "
                f"Protocolo {resultado['protocolo']}.")
    if nome == "incluir_assinatura":
        return (f"Abri a assinatura {n} de {resultado['produto_nome']}, {resultado['frequencia']}, "
                f"no mesmo endereço da assinatura {resultado['origem']}. Protocolo {resultado['protocolo']}. "
                f"A assinatura {resultado['origem']} continua como está.")
    return "Pronto."


def _pedir(nome: str, faltando: list[str]) -> str:
    pedidos = " e ".join(PERGUNTAS_FALTA[k] for k in faltando)
    return f"Para {ROTULOS[nome]}, {pedidos}."


def _esclarecer(decisao) -> str:
    top = [k for k, _ in sorted(decisao.probabilidades.items(), key=lambda x: -x[1]) if k in ROTULOS][:2]
    if len(top) >= 2:
        return f"Sobre a assinatura, você quer {ROTULOS[top[0]]} ou {ROTULOS[top[1]]}?"
    return "O que você quer fazer na assinatura: cancelar, trocar o produto, pausar ou mudar a entrega?"


def atender(provedor, estado: dict, tau: float, pendente: str | None) -> dict:
    """Escolhe uma capability e executa, pede o que falta, ou esclarece. Sem LLM gerativo."""
    decisao = provedor.decidir(estado, PERGUNTA)
    ultima = estado.get("ultima_mensagem_cliente") or ""
    blob = textos_cliente(estado)
    if decisao.confianca >= tau and decisao.intencao in REGISTRO:
        nome, motivo = decisao.intencao, "confiante"
    elif pendente and _so_preenche(pendente, blob, ultima):
        nome, motivo = pendente, "pendente"
    elif pendente and decisao.intencao == pendente:
        nome, motivo = pendente, "continuidade"
    else:
        pacote = _pacote(None, "baixa_confianca", decisao, False, pendente=None)
        pacote["resposta"] = _esclarecer(decisao)
        return pacote

    args, faltando = montar_args(nome, blob, ultima)
    if faltando:
        pacote = _pacote(nome, "faltam_dados", decisao, False, faltando, pendente=nome)
        pacote["capability"]["motivo_escolha"] = motivo
        pacote["resposta"] = _pedir(nome, faltando)
        return pacote

    resultado = REGISTRO[nome].executar(args)
    pacote = _pacote(nome, motivo, decisao, True, ferramentas=[{"ferramenta": nome, "args": args}])
    pacote["capability"]["resultado"] = resultado
    pacote["resposta"] = falar(nome, resultado)
    return pacote

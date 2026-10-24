"""Assinaturas fictícias da LojaExemplo e as operações que as capabilities executam.

Não há CPF nem login. O número da assinatura (50021 em diante) é a única chave,
no mesmo espírito do número de pedido. O estado fica em memória do processo.
"""
import copy, itertools
from datetime import date, timedelta

PRODUTOS = {
    "cafe_graos": "Café em grãos 250g",
    "capsulas": "Cápsulas de café",
    "racao": "Ração cães 3kg",
    "shampoo": "Shampoo",
    "filtro": "Filtro de água",
    "sabonete": "Sabonete líquido",
}
ALIASES = (
    ("café em grãos", "cafe_graos"), ("cafe em graos", "cafe_graos"), ("graos", "cafe_graos"), ("grãos", "cafe_graos"),
    ("cápsulas", "capsulas"), ("capsulas", "capsulas"),
    ("ração", "racao"), ("racao", "racao"),
    ("shampoo", "shampoo"), ("xampu", "shampoo"),
    ("filtro", "filtro"),
    ("sabonete", "sabonete"),
)
DIAS = {"semanal": 7, "quinzenal": 15, "mensal": 30}

_BASE = {
    "50021": {"produto": "cafe_graos", "frequencia": "mensal", "status": "ativa",
              "proxima_entrega": "2026-11-03", "endereco": "Rua das Flores, 120, São Paulo", "pagamento": "cartao"},
    "50022": {"produto": "racao", "frequencia": "quinzenal", "status": "ativa",
              "proxima_entrega": "2026-10-28", "endereco": "Av. Brasil, 900, Campinas", "pagamento": "pix"},
    "50023": {"produto": "capsulas", "frequencia": "mensal", "status": "pausada",
              "proxima_entrega": "2026-12-01", "endereco": "Rua do Café, 15, Santos", "pagamento": "cartao"},
    "50024": {"produto": "filtro", "frequencia": "mensal", "status": "cancelada",
              "proxima_entrega": None, "endereco": "Rua Augusta, 400, São Paulo", "pagamento": "boleto"},
    "50025": {"produto": "shampoo", "frequencia": "semanal", "status": "ativa",
              "proxima_entrega": "2026-10-27", "endereco": "Rua Harmonia, 88, São Paulo", "pagamento": "pix"},
}
ASSINATURAS: dict = {}
_protocolo = itertools.count(1)


def resetar():
    """Volta a base fictícia. Os testes chamam isso para não vazar estado entre casos."""
    global _protocolo
    ASSINATURAS.clear()
    ASSINATURAS.update(copy.deepcopy(_BASE))
    _protocolo = itertools.count(1)


def nome_produto(chave: str) -> str:
    return PRODUTOS.get(chave, chave)


def achar_produto(texto: str) -> str | None:
    t = texto.lower()
    for alias, chave in sorted(ALIASES, key=lambda a: len(a[0]), reverse=True):
        if alias in t:
            return chave
    return None


def _obter(numero: str):
    return ASSINATURAS.get(str(numero))


def _data(iso: str | None) -> str:
    if not iso:
        return "sem data"
    d = date.fromisoformat(iso)
    return d.strftime("%d/%m/%Y")


def _avancar(iso: str, frequencia: str, ciclos: int = 1) -> str:
    return (date.fromisoformat(iso) + timedelta(days=DIAS[frequencia] * ciclos)).isoformat()


def _proto(prefixo: str, numero: str) -> str:
    return f"{prefixo}-{numero}-{next(_protocolo):03d}"


def consultar(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    return {"numero": args["numero"], **a, "produto_nome": nome_produto(a["produto"]),
            "proxima_txt": _data(a["proxima_entrega"])}


def cancelar(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] == "cancelada":
        return {"erro": f"A assinatura {args['numero']} já está cancelada."}
    a["status"] = "cancelada"
    a["proxima_entrega"] = None
    return {"numero": args["numero"], "protocolo": _proto("CAN", args["numero"]),
            "produto_nome": nome_produto(a["produto"])}


def pausar(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] == "cancelada":
        return {"erro": f"A assinatura {args['numero']} está cancelada. Pausar não se aplica."}
    ciclos = max(1, int(args.get("ciclos") or 1))
    if a["proxima_entrega"]:
        a["proxima_entrega"] = _avancar(a["proxima_entrega"], a["frequencia"], ciclos)
    a["status"] = "pausada"
    return {"numero": args["numero"], "protocolo": _proto("PAU", args["numero"]),
            "ciclos": ciclos, "proxima_txt": _data(a["proxima_entrega"]), "produto_nome": nome_produto(a["produto"])}


def retomar(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] == "cancelada":
        return {"erro": f"A assinatura {args['numero']} está cancelada e não pode ser retomada."}
    if a["status"] != "pausada":
        return {"erro": f"A assinatura {args['numero']} já está ativa."}
    a["status"] = "ativa"
    return {"numero": args["numero"], "protocolo": _proto("RET", args["numero"]),
            "proxima_txt": _data(a["proxima_entrega"]), "produto_nome": nome_produto(a["produto"])}


def pular(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] != "ativa" or not a["proxima_entrega"]:
        return {"erro": f"A assinatura {args['numero']} está {a['status']}. Só pulo entrega de assinatura ativa."}
    a["proxima_entrega"] = _avancar(a["proxima_entrega"], a["frequencia"], 1)
    return {"numero": args["numero"], "protocolo": _proto("PUL", args["numero"]),
            "proxima_txt": _data(a["proxima_entrega"])}


def alterar_frequencia(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] == "cancelada":
        return {"erro": f"A assinatura {args['numero']} está cancelada."}
    if args["frequencia"] not in DIAS:
        return {"erro": "A frequência precisa ser semanal, quinzenal ou mensal."}
    a["frequencia"] = args["frequencia"]
    return {"numero": args["numero"], "protocolo": _proto("FRQ", args["numero"]),
            "frequencia": a["frequencia"], "proxima_txt": _data(a["proxima_entrega"])}


def alterar_endereco(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] == "cancelada":
        return {"erro": f"A assinatura {args['numero']} está cancelada."}
    a["endereco"] = args["endereco"].strip()
    return {"numero": args["numero"], "protocolo": _proto("END", args["numero"]), "endereco": a["endereco"]}


def trocar_produto(args: dict) -> dict:
    a = _obter(args["numero"])
    if not a:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if a["status"] == "cancelada":
        return {"erro": f"A assinatura {args['numero']} está cancelada, então não dá para trocar o produto."}
    if args["produto"] not in PRODUTOS:
        return {"erro": "Esse produto não está no catálogo de recorrência."}
    if a["produto"] == args["produto"]:
        return {"erro": f"A assinatura {args['numero']} já é de {nome_produto(a['produto'])}."}
    a["produto"] = args["produto"]
    return {"numero": args["numero"], "protocolo": _proto("TRC", args["numero"]),
            "produto_nome": nome_produto(a["produto"])}


def incluir(args: dict) -> dict:
    origem = _obter(args["numero"])
    if not origem:
        return {"erro": f"Não encontrei a assinatura {args['numero']}."}
    if args["produto"] not in PRODUTOS:
        return {"erro": "Esse produto não está no catálogo de recorrência."}
    novo = str(max(int(i) for i in ASSINATURAS) + 1)
    frequencia = args.get("frequencia") or "mensal"
    ASSINATURAS[novo] = {
        "produto": args["produto"], "frequencia": frequencia, "status": "ativa",
        "proxima_entrega": origem["proxima_entrega"] or "2026-11-24",
        "endereco": origem["endereco"], "pagamento": origem["pagamento"],
    }
    return {"numero": novo, "origem": args["numero"], "protocolo": _proto("INC", novo),
            "produto_nome": nome_produto(args["produto"]), "frequencia": frequencia,
            "endereco": origem["endereco"]}


resetar()

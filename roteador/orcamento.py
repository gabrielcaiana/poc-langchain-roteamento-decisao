"""Ledger de custo com teto rígido (persistido em runs/ledger.json).
Antes de cada chamada paga reservo o custo máximo estimado; se estourar o limite, aborto."""
import json, pathlib, threading
from .config import ROOT, CONFIG


class OrcamentoEstourado(RuntimeError):
    pass


class Ledger:
    def __init__(self, caminho=None, parar_em=None):
        self.caminho = pathlib.Path(caminho or ROOT / "runs/ledger.json")
        self.parar_em = float(parar_em if parar_em is not None else CONFIG["orcamento"]["parar_em_usd"])
        assert self.parar_em <= CONFIG["orcamento"]["teto_poc_usd"]
        self._lock = threading.Lock()
        self.dados = json.loads(self.caminho.read_text()) if self.caminho.exists() else {"gasto_usd": 0.0, "chamadas": 0, "por_modelo": {}}

    @property
    def gasto(self):
        return self.dados["gasto_usd"]

    def reservar(self, usd):
        if self.gasto + usd > self.parar_em:
            raise OrcamentoEstourado(f"gasto US${self.gasto:.4f} + reserva US${usd:.4f} > limite US${self.parar_em}")

    def registrar(self, modelo, usd):
        with self._lock:
            d = self.dados
            d["gasto_usd"] += usd; d["chamadas"] += 1
            d["por_modelo"][modelo] = d["por_modelo"].get(modelo, 0.0) + usd
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.caminho.write_text(json.dumps(d, indent=2))


class LedgerMemoria(Ledger):
    """Para testes: não toca no disco."""
    def __init__(self, parar_em=1.0):
        self.parar_em, self._lock = parar_em, threading.Lock()
        self.dados = {"gasto_usd": 0.0, "chamadas": 0, "por_modelo": {}}

    def registrar(self, modelo, usd):
        d = self.dados; d["gasto_usd"] += usd; d["chamadas"] += 1
        d["por_modelo"][modelo] = d["por_modelo"].get(modelo, 0.0) + usd

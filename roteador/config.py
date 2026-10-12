import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/config.json").read_text())
PRECOS = {k: v for k, v in json.loads((ROOT / "config/precos.json").read_text()).items() if not k.startswith("_")}

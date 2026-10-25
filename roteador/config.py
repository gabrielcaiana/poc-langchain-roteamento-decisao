import json, os, pathlib
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = os.environ["OPENAI_API_KEY"]

CONFIG = json.loads((ROOT / "config/config.json").read_text())
PRECOS = {k: v for k, v in json.loads((ROOT / "config/precos.json").read_text()).items() if not k.startswith("_")}

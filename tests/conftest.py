import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENROUTER_API_KEY", "teste-sem-chave-real")

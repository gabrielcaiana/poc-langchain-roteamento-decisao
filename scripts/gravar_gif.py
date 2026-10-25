"""Grava um GIF real da interface (Streamlit rodando local + chamadas reais ao OpenRouter) com Playwright."""
import pathlib, shutil, subprocess
from playwright.sync_api import sync_playwright
RAIZ = pathlib.Path(__file__).resolve().parents[1]
VID = RAIZ / "runs/video"; shutil.rmtree(VID, ignore_errors=True)
FALAS = ["não tô satisfeito",
         "o fone do pedido 10418 parou de funcionar, quero trocar",
         "aproveitando, vi que me cobraram duas vezes no pix, como fica?"]
W, H = 1280, 820
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(VID), record_video_size={"width": W, "height": H})
    pg = ctx.new_page(); pg.goto("http://localhost:8501")
    caixa = pg.get_by_test_id("stChatInputTextArea"); caixa.wait_for(timeout=60000); pg.wait_for_timeout(1500)
    for n, t in enumerate(FALAS, 1):
        caixa.click(); pg.keyboard.type(t, delay=55); pg.wait_for_timeout(400); pg.keyboard.press("Enter")
        pg.wait_for_function(f"document.querySelectorAll('[data-testid=stChatMessage]').length >= {2*n}", timeout=120000)
        pg.wait_for_timeout(600)
        pg.evaluate("document.querySelectorAll('[data-testid=stChatMessage]')[document.querySelectorAll('[data-testid=stChatMessage]').length-1].scrollIntoView({behavior:'smooth',block:'end'})")
        pg.wait_for_timeout(3500)
    pg.wait_for_timeout(1500)
    ctx.close(); b.close()
webm = next(VID.glob("*.webm"))
out = RAIZ / "evidencias/gifs/produto.gif"; out.parent.mkdir(parents=True, exist_ok=True)
filtro = "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-vf", filtro, "-loop", "0", str(out)], check=True)
subprocess.run(["gifsicle", "-O3", "--lossy=40", "--batch", str(out)], check=True)
dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(webm)], capture_output=True, text=True).stdout.strip()
print(out, out.stat().st_size, "bytes", dur, "s")

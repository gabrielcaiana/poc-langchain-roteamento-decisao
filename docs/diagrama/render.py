"""Renderiza o diagrama (rough.js + Excalifont) em frames e monta o GIF e o PNG estático (1200x627)."""
import pathlib, subprocess, shutil
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
FR = AQUI / "frames"; shutil.rmtree(FR, ignore_errors=True); FR.mkdir()
FPS, FADE, HOLD, FINAL = 12, 5, 9, 36
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1200, "height": 627})
    pg.goto((AQUI / "diagrama.html").as_uri()); pg.wait_for_timeout(1500)
    n = pg.evaluate("window.N"); i = 0
    def shot():
        global i; pg.screenshot(path=str(FR / f"f{i:04d}.png")); i += 1
    for k in range(n):
        for f in range(1, FADE + 1):
            pg.evaluate(f"mostrar({k},{f/FADE})"); shot()
        for _ in range(HOLD): shot()
    for _ in range(FINAL): shot()
    pg.evaluate(f"mostrar({n},0)"); pg.screenshot(path=str(RAIZ / "evidencias/arquitetura-thumb.png"))
    b.close()
out = RAIZ / "evidencias/gifs/arquitetura.gif"; out.parent.mkdir(parents=True, exist_ok=True)
pal = FR / "pal.png"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FR / "f%04d.png"), "-vf", "palettegen=max_colors=64", str(pal)], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FR / "f%04d.png"), "-i", str(pal),
                "-lavfi", "paletteuse=dither=none", "-loop", "0", str(out)], check=True)
subprocess.run(["gifsicle", "-O3", "--batch", str(out)], check=True)
shutil.rmtree(FR)
print(out, out.stat().st_size, "bytes", i / FPS, "s")

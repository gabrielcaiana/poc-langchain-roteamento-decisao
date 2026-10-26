"""Valida e renderiza os blocos ```mermaid de um README (mermaid.js no Chromium headless) em SVG + PNG 2x,
e troca cada bloco por imagem + fonte recolhida em <details>. Idempotente: blocos já dentro de <details> são re-renderizados.
Uso: python render_mermaid.py README.md evidencias/diagramas nome1 nome2 ...  (mermaid.min.js: npm i mermaid)"""
import pathlib, re, sys
from playwright.sync_api import sync_playwright

readme, outdir, nomes = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3:]
JS = pathlib.Path(__import__("os").environ.get("MERMAID_JS", "/workspace/excal/node_modules/mermaid/dist/mermaid.min.js"))
outdir.mkdir(parents=True, exist_ok=True)
texto = readme.read_text()
PADRAO = re.compile(r"(?:<details><summary>Fonte Mermaid</summary>\n\n)?```mermaid\n(.*?)```(?:\n\n</details>)?", re.S)
blocos = PADRAO.findall(texto)
assert len(blocos) == len(nomes), f"{len(blocos)} blocos, {len(nomes)} nomes"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(device_scale_factor=2, viewport={"width": 1400, "height": 900})
    pg.set_content("<html><body style='background:#fff;margin:0'><div id=c style='display:inline-block;padding:24px;background:#fff'></div></body></html>")
    pg.add_script_tag(path=str(JS))
    pg.evaluate("mermaid.initialize({startOnLoad:false, theme:'default', securityLevel:'loose', flowchart:{htmlLabels:true}, themeVariables:{fontSize:'18px'}})")
    for nome, src in zip(nomes, blocos, strict=True):
        r = pg.evaluate("""async (s) => { try { await mermaid.parse(s); const {svg} = await mermaid.render('g'+Date.now(), s);
                          const c=document.getElementById('c'); c.innerHTML = svg; const el=c.querySelector('svg'); const vb=el.viewBox.baseVal;
                          el.style.maxWidth='none'; el.setAttribute('width', vb.width); el.setAttribute('height', vb.height);
                          return {ok:true, svg: c.innerHTML}; } catch(e) { return {ok:false, err:String(e)}; } }""", src)
        if not r["ok"]:
            sys.exit(f"ERRO de sintaxe em {nome}: {r['err']}")
        svg = r["svg"]
        if "xmlns=" not in svg[:200]:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        svg = svg.replace("<svg", '<svg style="background-color:white"', 1)
        (outdir / f"{nome}.svg").write_text(svg)
        pg.locator("#c").screenshot(path=str(outdir / f"{nome}.png"))
        print("ok", nome)
    b.close()
it = iter(nomes)
rel = outdir.resolve().relative_to(readme.resolve().parent)
def troca(m):
    n = next(it)
    return (f"[![Diagrama {n}]({rel}/{n}.png)]({rel}/{n}.svg)\n\n<details><summary>Fonte Mermaid</summary>\n\n```mermaid\n{m.group(1)}```\n\n</details>")
novo = PADRAO.sub(troca, texto)
# remove imagem duplicada se o script rodar de novo
novo = re.sub(r"(\[!\[Diagrama [^\]]+\]\([^)]+\)\]\([^)]+\)\n\n)\1+", r"\1", novo)
readme.write_text(novo)

"""Tira screenshots reais da interface Streamlit rodando localmente (playwright headless)."""
from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
ROTEIROS = {
    "msd1": ["oi, meu tênis do pedido 10405 ainda não chegou, cadê?", "aproveitando, vi que me cobraram duas vezes esse pedido no pix",
             "aliás, você sabe se vai chover amanhã?", "não tô satisfeito"],
    "jev": ["comprei uma camiseta e ficou enorme em mim kkk", "é o 10454, chegou faz uns 5 dias", "não tô satisfeito"],
}


def enviar(page, texto, n):
    page.get_by_test_id("stChatInputTextArea").fill(texto)
    page.keyboard.press("Enter")
    page.wait_for_function(f"document.querySelectorAll('[data-testid=stChatMessage]').length >= {2*n}", timeout=90000)
    page.wait_for_timeout(1500)


with sync_playwright() as p:
    b = p.chromium.launch()
    for prov, falas in ROTEIROS.items():
        page = b.new_page(viewport={"width": 1500, "height": 1300})
        page.goto(URL); page.wait_for_selector("[data-testid=stChatInputTextArea]", timeout=60000)
        if prov != "msd1":
            page.get_by_test_id("stSelectbox").click(); page.get_by_role("option", name=prov, exact=True).click()
            page.wait_for_timeout(2500)
        for i, t in enumerate(falas, 1):
            enviar(page, t, i)
        page.screenshot(path=f"evidencias/screenshots/ui_{prov}.png", full_page=True)
    b.close()

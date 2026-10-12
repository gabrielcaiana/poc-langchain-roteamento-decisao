"""Interface mínima (Streamlit) para conversar com o bot e ver o roteamento de cada turno.
Rodar: streamlit run app.py"""
import uuid
import streamlit as st
from roteador.decisao import ClassificadorIntencao, criar_provedor
from roteador.grafo import construir_grafo, conversar
from roteador.llm import criar_llm
from roteador.orcamento import Ledger

st.set_page_config(page_title="LojaExemplo · atendimento", page_icon="💬", layout="wide")
CORES = {"devolucao": "🟣", "suporte": "🔵", "financeiro": "🟢", "fora_de_escopo": "⚪", "clarificacao": "🟠"}


@st.cache_resource
def montar(provedor: str):
    led = Ledger(); llm = criar_llm(led)
    return construir_grafo(ClassificadorIntencao(criar_provedor(provedor, led, llm)), llm), led


with st.sidebar:
    st.header("Camada de decisão")
    provedor = st.selectbox("Provedor", ["msd1", "jev", "msd1+fallback", "ab", "llm"])
    if st.button("Nova conversa") or "cid" not in st.session_state or st.session_state.get("prov") != provedor:
        st.session_state.update(cid=str(uuid.uuid4()), hist=[], prov=provedor)
    app, led = montar(provedor)
    st.caption(f"Conversa `{st.session_state.cid[:8]}` · gasto acumulado da POC: US${led.gasto:.4f}")

st.title("💬 LojaExemplo — atendimento pós-venda (fictício)")
col_chat, col_rota = st.columns([3, 2])
pergunta = st.chat_input("Escreva como um cliente escreveria…")
if pergunta:
    resp, d = conversar(app, st.session_state.cid, pergunta)
    st.session_state.hist.append((pergunta, resp, d))

with col_chat:
    for p, r, d in st.session_state.hist:
        st.chat_message("user").write(p)
        st.chat_message("assistant").markdown(f"**{CORES[d['destino']]} {d['destino']}**  \n{r}")
with col_rota:
    st.subheader("Roteamento por turno")
    for i, (p, r, d) in enumerate(st.session_state.hist, 1):
        with st.container(border=True):
            st.markdown(f"**Turno {i}** · `{d['provedor']}` → {CORES[d['destino']]} **{d['destino']}** ({d['motivo']}, τ={d['tau']})")
            st.progress(d["confianca"], text=" · ".join(f"{k} {v:.0%}" for k, v in sorted(d["probabilidades"].items(), key=lambda x: -x[1])))
            if d["ferramentas"]:
                st.caption("🛠 " + ", ".join(f["ferramenta"] for f in d["ferramentas"]))
            if "fallback_motivo" in d["extras"]:
                st.caption("⚠️ fallback: " + d["extras"]["fallback_motivo"])

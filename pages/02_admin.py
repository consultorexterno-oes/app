import streamlit as st
import pandas as pd
import sys
import os
import time
from datetime import datetime

# Ajuste de path para localizar módulos internos
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from configuracoes.config import COLUNAS_ID
from entrada_saida.funcoes_io import (
    carregar_previsto,
    salvar_base_dados,
    bump_version_token,
    get_version_token,
)
from api.graph_api import carregar_semana_ativa, salvar_apenas_aba

st.set_page_config(page_title="Admin - Rota 27", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
    :root { color-scheme: light !important; }
    .stButton>button { background-color: #033347 !important; color: white !important; border-radius: 6px; font-weight: bold; }
    .status-card { background-color: #fcfcfc; border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
    .card-label { font-size: 0.85em; color: #666; font-weight: bold; text-transform: uppercase; }
    .card-value { font-size: 1.3em; color: #033347; font-weight: bold; display: block; }
    .block-container { padding-top: 2rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- LOGO CENTRALIZADA ---
col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
with col_logo2:
    st.image("assets/Logo Rota 27.png", use_container_width=True)

# 1. Botão de Limpar Cache na Sidebar
with st.sidebar:
    st.image("assets/Logo Rota 27.png", width=100)
    st.markdown("### 🛠️ Ferramentas")
    if st.button("🧹 Limpar Cache do Sistema", key="btn_clear_cache"):
        st.cache_data.clear()
        bump_version_token()
        st.success("Cache limpo!")
        time.sleep(1)
        st.rerun()

# 2. Autenticação (Senha Master)
if not st.session_state.get("autenticado_admin", False):
    st.subheader("Página do Administrador - Acesso restrito 💻🔐")
    pw = st.text_input("Senha Master:", type="password")
    if st.button("Entrar"):
        if pw == "adm_oes":
            st.session_state.autenticado_admin = True
            st.rerun()
        else: st.error("Senha incorreta.")
    st.stop()

# 3. Carregamento de Dados
@st.cache_data(ttl=600)
def fetch_data(token):
    return carregar_previsto(token)

df_previsto = fetch_data(get_version_token())
controle = carregar_semana_ativa(version_token=get_version_token()) or {}

# 4. Lógica de Colunas e Datas
metadados_fixos = ["Revisão", "Cenário", "Semana", "Observações:", "ID", "DataHora"]
colunas_ignore = list(set(COLUNAS_ID + metadados_fixos))
cols_m = [c for c in df_previsto.columns if c not in colunas_ignore and pd.to_datetime(c, errors='coerce', dayfirst=True) is not pd.NaT]

# Função para formatar a data gigantesca em "Mes/Ano" (ex: Jan/26)
def formatar_data_resumida(val):
    try:
        dt = pd.to_datetime(val, dayfirst=True)
        # Lista de meses em PT-BR para garantir o formato desejado
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return f"{meses[dt.month-1]}/{str(dt.year)[2:]}"
    except:
        return str(val)

# Processa meses atualmente liberados
meses_liberados_raw = controle.get("meses", "")
lista_liberados = meses_liberados_raw.split(";") if meses_liberados_raw else []

# --- HEADER STATUS ---
st.title("⚙️ Painel de Controle Semanal")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="status-card"><span class="card-label">Semana Ativa</span><span class="card-value">{controle.get("semana", "---")}</span></div>', unsafe_allow_html=True)
with c2:
    status_texto = f"🔓 {len(lista_liberados)} meses liberados" if lista_liberados else "🔒 Edição Bloqueada"
    st.markdown(f'<div class="status-card"><span class="card-label">Status de Edição</span><span class="card-value">{status_texto}</span></div>', unsafe_allow_html=True)

tab_create, tab_edit, tab_view = st.tabs(["🆕 Criar Nova Semana", "🔧 Ajustes", "📊 Base Completa"])

# --- ABA 1: GERAR NOVA SEMANA (CLONAGEM + LIBERAÇÃO) ---
with tab_create:
    st.subheader("Clonagem de Revisão e Liberação de Período")
    with st.form("form_nova_semana"):
        c_a, c_b = st.columns(2)
        origem = c_a.selectbox("Copiar dados da revisão:", sorted(df_previsto["Revisão"].unique(), reverse=True))
        novo = c_b.text_input("Nome da nova semana:", placeholder="Ex: Semana 05 - v01")
        
        meses_novos = st.multiselect(
            "Selecione os meses que serão liberados para esta nova semana:",
            options=cols_m,
            default=cols_m,
            format_func=formatar_data_resumida, # AQUI APLICA O FORMATO Jan/26
            help="Os meses selecionados aqui serão os únicos editáveis pelos gerentes."
        )
        
        btn_executar = st.form_submit_button("🚀 Gerar e Ativar Ciclo")

    if btn_executar:
        if not novo:
            st.error("Por favor, dê um nome para a nova semana.")
        elif novo in df_previsto["Revisão"].unique():
            st.error("Esta semana já existe na base de dados.")
        else:
            with st.status("Clonando dados e configurando travas...", expanded=True) as status:
                df_nova = df_previsto[df_previsto["Revisão"] == origem].copy()
                df_nova["Revisão"] = novo
                salvar_base_dados(df_nova, append=True)
                
                str_meses = ";".join([str(m) for m in meses_novos])
                df_ctrl = pd.DataFrame({"Semana Ativa": [novo], "Meses Permitidos": [str_meses]})
                salvar_apenas_aba("Controle", df_ctrl)
                
                bump_version_token()
                status.update(label="✅ Nova Semana Ativada com Sucesso!", state="complete", expanded=False)
            
            st.balloons()
            time.sleep(1.5)
            st.rerun()

# --- ABA 2: AJUSTAR ATIVA (MANUTENÇÃO) ---
with tab_edit:
    st.subheader("Manutenção de Semana em Andamento")
    
    opcoes_rev = sorted(df_previsto["Revisão"].unique(), reverse=True)
    semana_atual_ctrl = controle.get("semana")
    idx_default = opcoes_rev.index(semana_atual_ctrl) if semana_atual_ctrl in opcoes_rev else 0
    
    col_x, col_y = st.columns(2)
    sel_ativa = col_x.selectbox("Mudar semana ativa para:", opcoes_rev, index=idx_default)
    
    meses_ajuste = col_y.multiselect(
        "Ajustar meses liberados:",
        options=cols_m,
        default=[m for m in cols_m if str(m) in lista_liberados],
        format_func=formatar_data_resumida # APLICA Jan/26 aqui também
    )
    
    if st.button("Salvar Ajustes"):
        with st.spinner("Atualizando controle..."):
            str_ajuste = ";".join([str(m) for m in meses_ajuste])
            df_m = pd.DataFrame({"Semana Ativa": [sel_ativa], "Meses Permitidos": [str_ajuste]})
            salvar_apenas_aba("Controle", df_m)
            bump_version_token()
            st.success("Ajustes aplicados!")
            time.sleep(1)
            st.rerun()

# --- ABA 3: VISUALIZAÇÃO ---
with tab_view:
    st.subheader("Visualização da Base de Dados")
    st.dataframe(df_previsto.sort_values("Revisão", ascending=False), use_container_width=True)
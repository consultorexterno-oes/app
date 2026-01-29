import streamlit as st
import pandas as pd
import time
import sys
import os
from datetime import datetime
from time import perf_counter

_start_total = time.time()
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from configuracoes.config import COLUNAS_ID
from entrada_saida.funcoes_io import (
    carregar_previsto_semana_ativa,
    salvar_base_dados,
    salvar_em_aba,
    get_version_token,
)
from api.graph_api import carregar_semana_ativa

# Configuração da página
st.set_page_config(page_title="Rota 27 - Refinado", layout="wide")

# --- Estilização Visual ---
st.markdown("""
    <style>
    :root { color-scheme: light !important; }
    .stButton>button { background-color: #033347 !important; color: white !important; border-radius: 8px; width: 100%; }
    .info-box { 
        font-size: 0.85rem; 
        color: #555; 
        background-color: #fcfcfc; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #eee;
        border-left: 5px solid #033347; 
        margin-bottom: 20px; 
    }
    .info-label { font-weight: bold; color: #033347; text-transform: uppercase; font-size: 0.75rem; }
    .status-badge { background-color: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- Funções de Suporte ---
def safe_to_datetime(val):
    if isinstance(val, (datetime, pd.Timestamp)):
        return val
    return pd.to_datetime(val, dayfirst=True, errors='coerce')

def init_state():
    defaults = {
        "autenticado": False, "df_previsto": None, "semana_nova": None,
        "edicoes": [], "has_unsaved_changes": False, "meses_disponiveis": [],
        "df_filtrado_cached": None, "filtro_coligada": "Todos",
        "filtro_gerencia": "Todos", "filtro_complexo": ["Todos"],
        "filtro_area": "Todos", "filtro_analise": ["Todos"]
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

init_state()

# --- Barra Lateral ---
with st.sidebar:
    st.image("assets/Logo Rota 27.png", width=150)
    st.markdown("### 🛠️ Sistema")
    if st.button("🧹 Limpar Cache e Reiniciar"):
        st.cache_data.clear()
        st.cache_resource.clear()
        for key in list(st.session_state.keys()):
            if key != "autenticado": del st.session_state[key]
        st.rerun()

# --- Login ---
if not st.session_state.autenticado:
    st.title("Refinado Semanal - Acesso")
    pw = st.text_input("Senha:", type="password")
    if st.button("Entrar"):
        if pw == "Narota27":
            st.session_state.autenticado = True
            st.rerun()
        else: st.error("Senha incorreta.")
    st.stop()

# --- Carregamento de Dados ---
if st.session_state.df_previsto is None:
    info = carregar_semana_ativa(version_token=get_version_token())
    if not info:
        st.error("Nenhuma semana ativa configurada.")
        st.stop()
    st.session_state.semana_nova = str(info.get("semana", ""))
    
    df_raw = carregar_previsto_semana_ativa(get_version_token())
    if "Cenário" in df_raw.columns:
        st.session_state.df_previsto = df_raw[df_raw["Cenário"].str.casefold() == "moderado"].copy()
    else:
        st.session_state.df_previsto = df_raw.copy()

df_base = st.session_state.df_previsto

# --- Identificação de Meses (Lógica para 2026) ---
if not st.session_state.meses_disponiveis:
    # Identifica colunas de data ignorando IDs
    cols = [c for c in df_base.columns if c not in COLUNAS_ID and pd.to_datetime(c, errors='coerce', dayfirst=True) is not pd.NaT]
    st.session_state.meses_disponiveis = cols

# --- UI Filtros ---
st.markdown(f"""<div class="info-box"><span class="info-label">Revisão:</span> {st.session_state.semana_nova} | <span class="status-badge">Edição Liberada para Todos os Meses</span></div>""", unsafe_allow_html=True)

st.subheader("Filtros de Visualização")
with st.form("form_filtros"):
    c1, c2, c3 = st.columns(3)
    op_col = ["Todos"] + sorted(df_base["Classificação"].unique().tolist())
    sel_col = c1.selectbox("Coligada", op_col, index=0)
    
    op_ger = ["Todos"] + sorted(df_base["Gerência"].unique().tolist())
    sel_ger = c2.selectbox("Gerência", op_ger, index=0)
    
    op_comp = ["Todos"] + sorted(df_base["Complexo"].unique().tolist())
    sel_comp = c3.multiselect("Complexo", op_comp, default=["Todos"])

    c4, c5 = st.columns(2)
    op_area = ["Todos"] + sorted(df_base["Área"].unique().tolist())
    sel_area = c4.selectbox("Área", op_area, index=0)
    
    # Filtro de Análise de Emissão corrigido
    op_ana = ["Todos"] + sorted(df_base["Análise de emissão"].unique().tolist())
    sel_ana = c5.multiselect("Análise de emissão", op_ana, default=["Todos"])

    if st.form_submit_button("Aplicar Filtros"):
        df_f = df_base.copy()
        if sel_col != "Todos": df_f = df_f[df_f["Classificação"] == sel_col]
        if sel_ger != "Todos": df_f = df_f[df_f["Gerência"] == sel_ger]
        if "Todos" not in sel_comp: df_f = df_f[df_f["Complexo"].isin(sel_comp)]
        if sel_area != "Todos": df_f = df_f[df_f["Área"] == sel_area]
        if "Todos" not in sel_ana: df_f = df_f[df_f["Análise de emissão"].isin(sel_ana)]
        st.session_state.df_filtrado_cached = df_f
        st.rerun()

df_work = st.session_state.df_filtrado_cached if st.session_state.df_filtrado_cached is not None else df_base

# --- Editor Refinado ---
st.subheader(f"Registros para Refinar: {len(df_work)}")
cols_edit = st.session_state.meses_disponiveis
cols_id_fixas = ["Classificação", "Gerência", "Complexo", "Área", "Análise de emissão"]

# Conversão para String para evitar erro de JSON no editor
df_input = df_work[cols_id_fixas + cols_edit].copy()
df_input.columns = [str(c) for c in df_input.columns]

config_colunas = {
    str(c): st.column_config.NumberColumn(safe_to_datetime(c).strftime("%b/%y"), format="R$ %.2f") 
    for c in cols_edit
}

df_editado = st.data_editor(
    df_input,
    column_config=config_colunas,
    disabled=cols_id_fixas,
    use_container_width=True,
    key="editor_refinado"
)

# --- Salvamento ---
if not df_editado.equals(df_input):
    st.session_state.has_unsaved_changes = True
    if st.button("💾 Salvar Alterações"):
        for idx in df_editado.index:
            for c in cols_edit:
                if df_editado.at[idx, str(c)] != df_input.at[idx, str(c)]:
                    st.session_state.df_previsto.at[idx, c] = df_editado.at[idx, str(c)]
        
        salvar_base_dados(st.session_state.df_previsto)
        st.success("Dados salvos com sucesso!")
        st.session_state.has_unsaved_changes = False
        st.rerun()

# --- Rodapé (CORREÇÃO DO VALUEERROR) ---
# O erro ocorria porque o 's' estava dentro da especificação de formato
st.sidebar.caption(f"Interação: {time.time() - _start_total:.2f}s")

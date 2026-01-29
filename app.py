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
    """Garante conversão correta de datas para evitar duplicidade Jan/26."""
    if isinstance(val, (datetime, pd.Timestamp)):
        return val
    return pd.to_datetime(val, dayfirst=True, errors='coerce')

def init_state():
    """Inicializa as variáveis de estado do Streamlit."""
    defaults = {
        "autenticado": False, 
        "df_previsto": None, 
        "semana_info": None, 
        "semana_nova": None,
        "meses_permitidos_admin": [], 
        "edicoes": [], 
        "has_unsaved_changes": False,
        "meses_disponiveis": [], 
        "meses_display": {}, 
        "df_semana_cached": None,
        "df_filtrado_cached": None, 
        "filtro_coligada": "Todos", 
        "filtro_gerencia": "Todos", 
        "filtro_complexo": ["Todos"],
        "filtro_area": "Todos", 
        "filtro_analise": ["Todos"]
    }
    for k, v in defaults.items():
        if k not in st.session_state: 
            st.session_state[k] = v

init_state()

# --- Barra Lateral (Cache e Controle) ---
with st.sidebar:
    st.image("assets/Logo Rota 27.png", width=150)
    st.markdown("### 🛠️ Sistema")
    if st.button("🔥 Reinicialização Profunda", help="Limpa todo o cache se o app não atualizar"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Cache limpo! Recarregando...")
        time.sleep(1)
        st.rerun()
    
    if st.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        # Reseta dados carregados mantendo a autenticação
        st.session_state.df_previsto = None
        st.session_state.df_semana_cached = None
        st.session_state.df_filtrado_cached = None
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
        st.error("Nenhuma semana ativa configurada pelo Administrador.")
        st.stop()
    
    st.session_state.semana_nova = str(info.get("semana", ""))
    
    # Processa os meses liberados (vem do Admin como ISO YYYY-MM-DD)
    permitidos = info.get("meses_permitidos", [])
    st.session_state.meses_permitidos_admin = [
        safe_to_datetime(m).strftime("%Y-%m-%d") for m in permitidos if pd.notnull(safe_to_datetime(m))
    ]
    
    df_raw = carregar_previsto_semana_ativa(get_version_token())
    # Filtro automático para o cenário Moderado conforme regra de negócio
    if "Cenário" in df_raw.columns:
        st.session_state.df_previsto = df_raw[df_raw["Cenário"].str.casefold() == "moderado"].copy()
    else:
        st.session_state.df_previsto = df_raw.copy()

# --- Cabeçalho Informativo ---
st.markdown(f"""
    <div class="info-box">
        <span class="info-label">Revisão Ativa:</span> {st.session_state.semana_nova} &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="info-label">Status:</span> <span class="status-badge">Edição Liberada</span>
    </div>
""", unsafe_allow_html=True)

VALORES_ANALISE = ["RECEITA MAO DE OBRA", "RECEITA LOCAÇÃO", "RECEITA DE INDENIZAÇÃO", "CUSTO COM MAO DE OBRA", "CUSTO COM INSUMOS", "LOCAÇÃO DE EQUIPAMENTOS"]

# --- Filtro de Emissão ---
if st.session_state.df_semana_cached is None:
    df_s = st.session_state.df_previsto[st.session_state.df_previsto["Análise de emissão"].isin(VALORES_ANALISE)].copy()
    st.session_state.df_semana_cached = df_s

df_semana = st.session_state.df_semana_cached

# --- Identificação das Colunas de Edição ---
if not st.session_state.meses_disponiveis:
    cols = [c for c in df_semana.columns if c not in COLUNAS_ID and pd.to_datetime(c, errors='coerce', dayfirst=True) is not pd.NaT]
    
    if st.session_state.meses_permitidos_admin:
        cols = [c for c in cols if safe_to_datetime(c).strftime("%Y-%m-%d") in st.session_state.meses_permitidos_admin]
        
    st.session_state.meses_disponiveis = cols
    st.session_state.meses_display = {str(m): safe_to_datetime(m).strftime("%b/%y") for m in cols}

# --- Filtros de Tela ---
st.subheader("Filtros")
with st.form("form_filtros"):
    c1, c2, c3 = st.columns(3)
    op_col = ["Todos"] + sorted(df_semana["Classificação"].unique().tolist())
    sel_col = c1.selectbox("Coligada", op_col, index=0)
    
    op_ger = ["Todos"] + sorted(df_semana["Gerência"].unique().tolist())
    sel_ger = c2.selectbox("Gerência", op_ger, index=0)
    
    op_comp = ["Todos"] + sorted(df_semana["Complexo"].unique().tolist())
    sel_comp = c3.multiselect("Complexo", op_comp, default=["Todos"])

    if st.form_submit_button("Aplicar Filtros"):
        df_f = df_semana.copy()
        if sel_col != "Todos": df_f = df_f[df_f["Classificação"] == sel_col]
        if sel_ger != "Todos": df_f = df_f[df_f["Gerência"] == sel_ger]
        if "Todos" not in sel_comp: df_f = df_f[df_f["Complexo"].isin(sel_comp)]
        st.session_state.df_filtrado_cached = df_f
        st.rerun()

df_work = st.session_state.df_filtrado_cached if st.session_state.df_filtrado_cached is not None else df_semana

# --- EDITOR DE DADOS (CORREÇÃO TYPEERROR) ---
# O erro ocorria porque o Streamlit não aceitava objetos Timestamp/Datetime no JSON do editor
st.subheader(f"Editor: {len(df_work)} registros")

cols_id_fixas = ["Classificação", "Gerência", "Complexo", "Área", "Análise de emissão"]
cols_edit = st.session_state.meses_disponiveis

# Criamos o DF de entrada garantindo que TODOS os nomes de colunas sejam STRINGS
df_input = df_work[cols_id_fixas + cols_edit].copy()
df_input.columns = [str(c) for c in df_input.columns]

# Criamos a configuração das colunas também usando chaves em STRING
config_colunas = {
    str(m): st.column_config.NumberColumn(
        st.session_state.meses_display.get(str(m), str(m)), 
        format="R$ %.2f", 
        min_value=0.0
    ) for m in cols_edit
}

df_editado = st.data_editor(
    df_input,
    column_config=config_colunas,
    disabled=cols_id_fixas,
    use_container_width=True,
    num_rows="fixed",
    key="editor_refinado"
)

# --- Processamento de Salvamento ---
if not df_editado.equals(df_input):
    st.session_state.has_unsaved_changes = True
    changes = []
    # Compara linha a linha para detectar o que mudou
    for idx in df_editado.index:
        for m in cols_edit:
            m_str = str(m)
            if df_editado.at[idx, m_str] != df_input.at[idx, m_str]:
                row = df_editado.loc[idx]
                changes.append({
                    "index": idx, "Mês": m, "Novo Valor": row[m_str], 
                    "Semana": st.session_state.semana_nova, "DataHora": pd.Timestamp.now(),
                    "Gerência": row["Gerência"], "Análise de emissão": row["Análise de emissão"]
                })
    st.session_state.edicoes = changes

if st.session_state.has_unsaved_changes:
    if st.button("💾 Salvar Alterações"):
        try:
            with st.spinner("Gravando dados..."):
                for ed in st.session_state.edicoes:
                    # Aplica a mudança no dataframe original (mês original pode ser data ou string)
                    st.session_state.df_previsto.at[ed["index"], ed["Mês"]] = ed["Novo Valor"]
                
                salvar_base_dados(st.session_state.df_previsto)
                salvar_em_aba(pd.DataFrame(st.session_state.edicoes), aba="Histórico")
                
                st.session_state.has_unsaved_changes = False
                st.session_state.df_semana_cached = None # Força recarga no próximo loop
                st.success("Dados salvos com sucesso!")
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

# Rodapé de debug/info
st.sidebar.markdown("---")
st.sidebar.caption(f"⏱️ Última interação: {time.time() - _start_total:.2f}s")

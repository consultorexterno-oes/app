import streamlit as st
import pandas as pd
import time
import sys
import os
from datetime import datetime
from time import perf_counter

_start_total = time.time()
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from configuracoes.config import COLUNAS_ID, COLUNAS_MESES
from entrada_saida.funcoes_io import (
    carregar_previsto_semana_ativa,
    salvar_base_dados,
    salvar_em_aba,
    get_version_token,
)
from api.graph_api import carregar_semana_ativa

st.set_page_config(page_title="Rota 27", layout="wide")

# --- Estilização Visual ---
st.markdown(f"""
    <style>
    :root {{ color-scheme: light !important; }}
    .stButton>button {{ background-color: #033347 !important; color: white !important; border-radius: 8px; width: 100%; }}
    section[data-testid="stSidebar"] li:nth-of-type(1) a p {{ visibility: hidden; position: relative; }}
    section[data-testid="stSidebar"] li:nth-of-type(1) a p::after {{ content: 'Preencher Refinado'; visibility: visible; position: absolute; top: 0; left: 0; }}
    section[data-testid="stSidebar"] li:nth-of-type(2) a p {{ visibility: hidden; position: relative; }}
    section[data-testid="stSidebar"] li:nth-of-type(2) a p::after {{ content: 'Gerenciar Semanas'; visibility: visible; position: absolute; top: 0; left: 0; }}
    
    .info-box {{ 
        font-size: 0.85rem; 
        color: #555; 
        background-color: #f9f9f9; 
        padding: 12px; 
        border-radius: 8px; 
        border: 1px solid #eee;
        border-left: 5px solid #E2725B; 
        margin-bottom: 20px; 
    }}
    .info-label {{ font-weight: bold; color: #033347; text-transform: uppercase; font-size: 0.75rem; }}
    </style>
""", unsafe_allow_html=True)

def init_state():
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
        "filtros_aplicados": False,
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

st.image("assets/Logo Rota 27.png", width=400)
st.title("Refinado Semanal - Preenchimento")

if not st.session_state.autenticado:
    pw = st.text_input("Senha:", type="password")
    if st.button("Entrar"):
        if pw == "Narota27":
            st.session_state.autenticado = True
            st.rerun()
        else: 
            st.error("Incorreta.")
    st.stop()

if st.sidebar.button("🔄 Recarregar Dados"):
    st.cache_data.clear()
    keys_to_keep = ["autenticado"]
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
    st.rerun()

def _filtrar_moderado(df):
    return df[df["Cenário"].str.casefold() == "moderado"].copy() if "Cenário" in df.columns else df

# --- Carregamento de Dados ---
if st.session_state.df_previsto is None:
    info = carregar_semana_ativa(version_token=get_version_token())
    if not info: 
        st.error("Nenhuma semana ativa configurada.")
        st.stop()
    
    st.session_state.semana_info = info
    st.session_state.semana_nova = str(info.get("semana", ""))
    # Garantimos que a lista de meses permitidos venha limpa
    permitidos = info.get("meses_permitidos", [])
    st.session_state.meses_permitidos_admin = [str(m).strip() for m in permitidos if m]
    
    df = _filtrar_moderado(carregar_previsto_semana_ativa(get_version_token()))
    st.session_state.df_previsto = df

# --- Formatação dos Meses (DEDUPLICADO) ---
meses_formatados = []
for m in st.session_state.meses_permitidos_admin:
    try:
        dt = pd.to_datetime(m, dayfirst=True)
        txt = dt.strftime("%b/%y").capitalize()
        if txt not in meses_formatados: # Evita Jan/26, Jan/26
            meses_formatados.append(txt)
    except:
        if str(m) not in meses_formatados:
            meses_formatados.append(str(m))
meses_texto = ", ".join(meses_formatados)

st.markdown(f"""
    <div class="info-box">
        <span class="info-label">Revisão Ativa:</span> {st.session_state.semana_nova} &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="info-label">Meses Liberados para Edição:</span> {meses_texto if meses_texto else 'Nenhum'}
    </div>
""", unsafe_allow_html=True)

VALORES_ANALISE = ["RECEITA MAO DE OBRA", "RECEITA LOCAÇÃO", "RECEITA DE INDENIZAÇÃO", "CUSTO COM MAO DE OBRA", "CUSTO COM INSUMOS", "LOCAÇÃO DE EQUIPAMENTOS"]

if st.session_state.df_semana_cached is None:
    df_s = st.session_state.df_previsto[st.session_state.df_previsto["Análise de emissão"].isin(VALORES_ANALISE)].copy()
    df_s["Análise de emissão"] = pd.Categorical(df_s["Análise de emissão"], categories=VALORES_ANALISE, ordered=True)
    st.session_state.df_semana_cached = df_s.sort_values("Análise de emissão")

df_semana = st.session_state.df_semana_cached

if not st.session_state.meses_disponiveis:
    cols = [c for c in df_semana.columns if c not in COLUNAS_ID and pd.to_datetime(c, errors='coerce', dayfirst=True) is not pd.NaT]
    if st.session_state.meses_permitidos_admin:
        # Normalização para comparação: converte ambos para string de data simples
        def normalize(x): return str(pd.to_datetime(x, dayfirst=True).date())
        permitidos_norm = [normalize(m) for m in st.session_state.meses_permitidos_admin]
        cols = [c for c in cols if normalize(c) in permitidos_norm]
        
    st.session_state.meses_disponiveis = cols
    st.session_state.meses_display = {m: pd.to_datetime(m, dayfirst=True).strftime("%b/%y") for m in cols}

# --- Filtros ---
st.subheader("Filtros")
with st.form("form_filtros"):
    c1, c2, c3 = st.columns(3)
    op_col = ["Todos"] + sorted(df_semana["Classificação"].unique().tolist())
    sel_col = c1.selectbox("Coligada", op_col, index=op_col.index(st.session_state.filtro_coligada) if st.session_state.filtro_coligada in op_col else 0)

    op_ger = ["Todos"] + sorted(df_semana["Gerência"].unique().tolist())
    sel_ger = c2.selectbox("Gerência", op_ger, index=op_ger.index(st.session_state.filtro_gerencia) if st.session_state.filtro_gerencia in op_ger else 0)

    base_comp = df_semana if sel_ger == "Todos" else df_semana[df_semana["Gerência"] == sel_ger]
    op_comp = ["Todos"] + sorted(base_comp["Complexo"].unique().tolist())
    sel_comp = c3.multiselect("Complexo", op_comp, default=st.session_state.filtro_complexo)

    c4, c5 = st.columns(2)
    base_area = df_semana
    if sel_comp and "Todos" not in sel_comp: base_area = df_semana[df_semana["Complexo"].isin(sel_comp)]
    elif sel_ger != "Todos": base_area = df_semana[df_semana["Gerência"] == sel_ger]
    
    op_area = ["Todos"] + sorted(base_area["Área"].unique().tolist())
    sel_area = c4.selectbox("Área", op_area, index=op_area.index(st.session_state.filtro_area) if st.session_state.filtro_area in op_area else 0)
    
    op_ana = ["Todos"] + [v for v in VALORES_ANALISE if v in df_semana["Análise de emissão"].unique()]
    sel_ana = c5.multiselect("Análise de emissão", op_ana, default=st.session_state.filtro_analise)

    if st.form_submit_button("Aplicar Filtros"):
        def tratar_mutex(lista):
            if len(lista) > 1 and "Todos" in lista:
                if lista[-1] == "Todos": return ["Todos"]
                else: return [x for x in lista if x != "Todos"]
            return lista if lista else ["Todos"]

        sel_comp = tratar_mutex(sel_comp)
        sel_ana = tratar_mutex(sel_ana)

        df_f = df_semana.copy()
        if sel_col != "Todos": df_f = df_f[df_f["Classificação"] == sel_col]
        if sel_ger != "Todos": df_f = df_f[df_f["Gerência"] == sel_ger]
        if "Todos" not in sel_comp: df_f = df_f[df_f["Complexo"].isin(sel_comp)]
        if sel_area != "Todos": df_f = df_f[df_f["Área"] == sel_area]
        if "Todos" not in sel_ana: df_f = df_f[df_f["Análise de emissão"].isin(sel_ana)]
        
        st.session_state.df_filtrado_cached = df_f
        st.session_state.filtro_coligada = sel_col
        st.session_state.filtro_gerencia = sel_ger
        st.session_state.filtro_complexo = sel_comp
        st.session_state.filtro_area = sel_area
        st.session_state.filtro_analise = sel_ana
        st.rerun()

df_work = st.session_state.df_filtrado_cached if st.session_state.df_filtrado_cached is not None else df_semana

# --- Editor ---
st.subheader(f"Edição: {len(df_work)} registros encontrados")
cols_id_fixas = ["Classificação", "Gerência", "Complexo", "Área", "Análise de emissão"]
cols_edit = st.session_state.meses_disponiveis

df_input = df_work[cols_id_fixas + cols_edit].copy()
for c in cols_edit: 
    df_input[c] = pd.to_numeric(df_input[c], errors='coerce').fillna(0.0)

df_editado = st.data_editor(
    df_input,
    column_config={
        m: st.column_config.NumberColumn(st.session_state.meses_display.get(m, m), format="R$ %.2f", min_value=0.0) 
        for m in cols_edit
    },
    disabled=cols_id_fixas,
    use_container_width=True,
    num_rows="fixed",
    key="editor_refinado"
)

if not df_editado.equals(df_input):
    st.session_state.has_unsaved_changes = True
    changes = []
    for idx in df_editado.index:
        for m in cols_edit:
            if df_editado.at[idx, m] != df_input.at[idx, m]:
                row = df_editado.loc[idx]
                changes.append({
                    "index": idx, "Mês": m, "Novo Valor": row[m], "Semana": st.session_state.semana_nova,
                    "DataHora": pd.Timestamp.now(), "Classificação": row["Classificação"], 
                    "Gerência": row["Gerência"], "Complexo": row["Complexo"], "Área": row["Área"], 
                    "Análise de emissão": row["Análise de emissão"]
                })
    st.session_state.edicoes = changes

c_salvar, c_info = st.columns([1, 3])
if c_salvar.button("💾 Salvar Alterações", disabled=not st.session_state.has_unsaved_changes):
    try:
        with st.spinner("Salvando no SharePoint..."):
            for ed in st.session_state.edicoes:
                st.session_state.df_previsto.at[ed["index"], ed["Mês"]] = ed["Novo Valor"]
            
            df_para_gravar = st.session_state.df_previsto.copy()
            salvar_base_dados(df_para_gravar)
            salvar_em_aba(pd.DataFrame(st.session_state.edicoes), aba="Histórico")
            
            st.session_state.has_unsaved_changes = False
            st.session_state.edicoes = []
            st.session_state.df_semana_cached = None 
            st.success("Tudo salvo com sucesso!")
            time.sleep(1)
            st.rerun()
    except Exception as e: 
        st.error(f"Erro ao salvar: {e}")

if st.session_state.has_unsaved_changes:
    c_info.warning(f"⚠️ Existem {len(st.session_state.edicoes)} células alteradas. Clique em 'Salvar' para confirmar.")

st.sidebar.markdown("---")
st.sidebar.caption(f"📅 **Configuração Atual**")
st.sidebar.caption(f"Semana: {st.session_state.semana_nova}")
st.sidebar.caption(f"Meses: {meses_texto}")
st.sidebar.write(f"⏱️ Interação: {time.time() - _start_total:.2f}s")

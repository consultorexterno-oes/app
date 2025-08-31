import streamlit as st
import pandas as pd
import time
import sys
import os
from io import BytesIO
from datetime import datetime
from time import perf_counter
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ============================
# Timer geral do app
# ============================
_start_total = time.time()

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from configuracoes.config import COLUNAS_ID, COLUNAS_MESES
from entrada_saida.funcoes_io import (
    carregar_previsto,
    carregar_previsto_semana_ativa,
    salvar_base_dados,
    salvar_em_aba,
    get_version_token,
)

from api.graph_api import carregar_semana_ativa

# ============================
# Cores e estilo
# ============================
bg_color = "#FFFFFF"
fg_color = "#000000"
accent_color = "#033347"

st.set_page_config(page_title="Rota 27", layout="wide")

st.markdown(
    f"""
    <style>
    :root {{
        color-scheme: light !important;
    }}
    body {{
        background-color: {bg_color} !important;
        color: {fg_color} !important;
    }}
    [data-testid="stHeader"], [data-testid="stSidebar"] {{
        background-color: {bg_color} !important;
        color: {fg_color} !important;
    }}
    .stButton>button {{
        background-color: {accent_color} !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.5em 1em;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(1) a p {{
        visibility: hidden; position: relative;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(1) a p::after {{
        content: 'Preencher Refinado'; visibility: visible; position: absolute; top: 0; left: 0;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(2) a p {{
        visibility: hidden; position: relative;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(2) a p::after {{
        content: 'Gerenciar Semanas'; visibility: visible; position: absolute; top: 0; left: 0;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ============================
# Helpers de estado
# ============================
def init_state():
    defaults = {
        "autenticado": False,
        "df_previsto": None,              # base SOMENTE da semana ativa
        "semana_info": None,
        "semana_nova": None,
        "meses_permitidos_admin": [],
        "edicoes": [],
        "has_unsaved_changes": False,
        "meses_disponiveis": [],
        "meses_display": {},
        "df_semana_cache_key": None,
        "df_semana_cached": None,
        "filtros_aplicados": False,
        "df_filtrado_cached": None,
        "limite_preview_linhas": 5000,
        "filtro_coligada": "Todos",
        "filtro_gerencia": "Todos",
        "filtro_complexo": "Todos",
        "filtro_area": "Todos",
        "filtro_analise": "Todos",
        "_boot_done": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ============================
# Logo e título
# ============================
st.image("assets/Logo Rota 27.png", width=400)
st.title("Refinado Semanal - Preenchimento")
st.subheader("🚧 Versão Beta: Aplicativo em desenvolvimento...")

# ============================
# Autenticação
# ============================
if not st.session_state.autenticado:
    st.subheader("Acesso restrito")
    password_input = st.text_input("Digite a senha:", type="password")
    if st.button("Entrar"):
        if password_input == "Narota27":
            st.session_state.autenticado = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

# ============================
# Função utilitária para filtrar Moderado
# ============================
def _filtrar_moderado(df: pd.DataFrame) -> pd.DataFrame:
    if "Cenário" not in df.columns:
        return df
    return df[df["Cenário"].str.casefold() == "moderado"].copy()

# ============================
# Carga inicial (1x)
# ============================
def _carregar_base_somente_uma_vez() -> pd.DataFrame:
    if st.session_state.df_previsto is not None:
        return st.session_state.df_previsto

    t0 = perf_counter()

    with st.spinner("Lendo semana ativa…"):
        semana_info = carregar_semana_ativa(version_token=get_version_token())
        if not semana_info:
            st.sidebar.warning("Nenhuma semana ativa definida na aba 'Controle'.")
            st.stop()
        st.session_state.semana_info = semana_info

    semana_ativa = str(st.session_state.semana_info.get("semana", ""))
    meses_controle = st.session_state.semana_info.get("meses_permitidos", []) or []

    with st.spinner(f"Carregando dados da semana '{semana_ativa}'…"):
        df = carregar_previsto_semana_ativa(get_version_token())

    # Só mantém Moderado
    df = _filtrar_moderado(df)

    # Ajusta meses
    COLUNAS_MESES.clear()
    cols_meses = [
        c for c in df.columns
        if c not in COLUNAS_ID and pd.notnull(pd.to_datetime(c, errors="coerce", dayfirst=True))
    ]
    COLUNAS_MESES.extend(cols_meses)

    st.session_state.df_previsto = df
    st.session_state.semana_nova = semana_ativa
    st.session_state.meses_permitidos_admin = meses_controle

    st.sidebar.success(f"Carga inicial concluída em {perf_counter()-t0:.2f}s")
    st.session_state._boot_done = True
    return df

_carregar_base_somente_uma_vez()

# ============================
# Sincronização da semana ativa
# ============================
st.sidebar.success(f"Semana ativa: {st.session_state.semana_nova}")
if st.session_state.meses_permitidos_admin:
    st.sidebar.info(f"Meses permitidos: {len(st.session_state.meses_permitidos_admin)}")

# ============================
# Botão recarregar manual
# ============================
def resetar_cache_e_estado():
    st.cache_data.clear()
    for key in [
        "df_previsto","semana_info","semana_nova","meses_permitidos_admin",
        "edicoes","has_unsaved_changes","meses_disponiveis","meses_display",
        "df_semana_cache_key","df_semana_cached","df_filtrado_cached","filtros_aplicados",
        "_boot_done"
    ]:
        if key in st.session_state:
            del st.session_state[key]
    init_state()

if st.sidebar.button("Recarregar dados da origem"):
    resetar_cache_e_estado()
    st.rerun()

# ============================
# Preparação da semana (memória)
# ============================
VALORES_ANALISE = [
    "RECEITA MAO DE OBRA",
    "RECEITA LOCAÇÃO",
    "RECEITA DE INDENIZAÇÃO",
    "CUSTO COM MAO DE OBRA",
    "CUSTO COM INSUMOS",
    "LOCAÇÃO DE EQUIPAMENTOS"
]

def preparar_df_semana(df_previsto: pd.DataFrame) -> pd.DataFrame:
    df = df_previsto[df_previsto["Análise de emissão"].isin(VALORES_ANALISE)].copy()
    if df.empty:
        return df
    df["Análise de emissão"] = pd.Categorical(df["Análise de emissão"], categories=VALORES_ANALISE, ordered=True)
    df.sort_values("Análise de emissão", inplace=True)
    return df

_cache_key = (id(st.session_state.df_previsto), st.session_state.semana_nova)
if st.session_state.df_semana_cache_key != _cache_key:
    st.session_state.df_semana_cached = preparar_df_semana(st.session_state.df_previsto)
    st.session_state.df_semana_cache_key = _cache_key

df_semana = st.session_state.df_semana_cached
if df_semana is None or df_semana.empty:
    st.warning(f"Nenhuma linha para a semana '{st.session_state.semana_nova}'.")
    st.stop()

# ============================
# Meses permitidos (pré-cálculo)
# ============================
def _extrair_meses_validos(df_ref: pd.DataFrame):
    cols_meses = [
        c for c in df_ref.columns
        if c not in COLUNAS_ID + ["Observações:"]
        and pd.notnull(pd.to_datetime(c, errors="coerce", dayfirst=True))
    ]
    if st.session_state.meses_permitidos_admin:
        cols_meses = [m for m in cols_meses if m in st.session_state.meses_permitidos_admin]
    display_map = {m: pd.to_datetime(m, dayfirst=True).strftime("%B %Y").capitalize() for m in cols_meses}
    return cols_meses, display_map

if not st.session_state.meses_disponiveis or not st.session_state.meses_display:
    meses_disponiveis, meses_display = _extrair_meses_validos(df_semana)
    st.session_state.meses_disponiveis = meses_disponiveis
    st.session_state.meses_display = meses_display

# ============================
# Filtros (aplicação sob demanda via form)
# ============================
st.subheader("Filtros para Visualização")

with st.form("form_filtros", clear_on_submit=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        opcoes_coligada = ["Todos"] + sorted(df_semana["Classificação"].dropna().unique().tolist())
        coligada_filtro = st.selectbox(
            "Coligada",
            opcoes_coligada,
            index=opcoes_coligada.index(st.session_state.filtro_coligada)
            if st.session_state.filtro_coligada in opcoes_coligada else 0
        )

    with col2:
        opcoes_gerencia = ["Todos"] + sorted(df_semana["Gerência"].dropna().unique().tolist())
        gerencia_filtro = st.selectbox(
            "Gerência",
            opcoes_gerencia,
            index=opcoes_gerencia.index(st.session_state.filtro_gerencia)
            if st.session_state.filtro_gerencia in opcoes_gerencia else 0
        )

    with col3:
        if gerencia_filtro == "Todos":
            opcoes_complexo = sorted(df_semana["Complexo"].dropna().unique().tolist())
        else:
            opcoes_complexo = sorted(
                df_semana.loc[df_semana["Gerência"] == gerencia_filtro, "Complexo"].dropna().unique().tolist()
            )
        opcoes_complexo = ["Todos"] + opcoes_complexo

        complexos_selecionados = st.multiselect(
            "Complexo",
            options=opcoes_complexo,
            default=(
                [st.session_state.filtro_complexo]
                if st.session_state.filtro_complexo in opcoes_complexo
                else ["Todos"]
            )
        )

    col4, col5 = st.columns(2)
    with col4:
        if not complexos_selecionados or "Todos" in complexos_selecionados:
            if gerencia_filtro == "Todos":
                opcoes_area = ["Todos"] + sorted(df_semana["Área"].dropna().unique().tolist())
            else:
                opcoes_area = ["Todos"] + sorted(
                    df_semana.loc[df_semana["Gerência"] == gerencia_filtro, "Área"].dropna().unique().tolist()
                )
        else:
            opcoes_area = ["Todos"] + sorted(
                df_semana.loc[df_semana["Complexo"].isin(complexos_selecionados), "Área"].dropna().unique().tolist()
            )

        area_filtro = st.selectbox(
            "Área",
            opcoes_area,
            index=opcoes_area.index(st.session_state.filtro_area)
            if st.session_state.filtro_area in opcoes_area else 0
        )

    with col5:
        opcoes_analise = ["Todos"] + [
            v for v in VALORES_ANALISE if v in df_semana["Análise de emissão"].unique()
        ]
        analise_filtro = st.selectbox(
            "Análise de emissão",
            opcoes_analise,
            index=opcoes_analise.index(st.session_state.filtro_analise)
            if st.session_state.filtro_analise in opcoes_analise else 0
        )

    aplicar = st.form_submit_button("Aplicar filtros")


# Só filtra quando o usuário clicar
if aplicar or not st.session_state.filtros_aplicados:
    df_filtrado = df_semana.copy()
    if coligada_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Classificação"] == coligada_filtro]
    if gerencia_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Gerência"] == gerencia_filtro]
    if complexos_selecionados and "Todos" not in complexos_selecionados:
        df_filtrado = df_filtrado[df_filtrado["Complexo"].isin(complexos_selecionados)]
    if area_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Área"] == area_filtro]
    if analise_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Análise de emissão"] == analise_filtro]

    st.session_state.df_filtrado_cached = df_filtrado
    st.session_state.filtros_aplicados = True
    st.session_state.filtro_coligada = coligada_filtro
    st.session_state.filtro_gerencia = gerencia_filtro
    st.session_state.filtro_complexo = complexos_selecionados  # agora guarda lista
    st.session_state.filtro_area = area_filtro
    st.session_state.filtro_analise = analise_filtro

# Sempre garante df_filtrado antes de usar
df_filtrado = (
    st.session_state.df_filtrado_cached
    if st.session_state.df_filtrado_cached is not None
    else df_semana
)

# ============================
# Edição de Valores (nova lógica)
# ============================
st.subheader("Edição de Valores")

df_editavel = df_filtrado.copy()


# Converte colunas de meses para float (garante que o number_input funcione)
for col in st.session_state.meses_disponiveis:
    df_editavel[col] = pd.to_numeric(df_editavel[col], errors="coerce").fillna(0.0)

# Cria inputs para cada linha x mês
edicoes = []
for idx, row in df_editavel.iterrows():
    st.markdown(f"**{row['Classificação']} - {row['Gerência']} - {row['Complexo']} - {row['Área']} - {row['Análise de emissão']}**")
    cols = st.columns(len(st.session_state.meses_disponiveis))
    novos_valores = {}
    for i, mes in enumerate(st.session_state.meses_disponiveis):
        with cols[i]:
            novos_valores[mes] = st.number_input(
                st.session_state.meses_display.get(mes, mes),
                value=float(row[mes]),
                step=100.0,
                key=f"edit_{idx}_{mes}"
            )
    # guarda edições
    for mes, novo_valor in novos_valores.items():
        if novo_valor != row[mes]:
            edicoes.append({
                "index": idx,
                "Classificação": row["Classificação"],
                "Gerência": row["Gerência"],
                "Complexo": row["Complexo"],
                "Área": row["Área"],
                "Análise de emissão": row["Análise de emissão"],
                "Mês": mes,
                "Novo Valor": novo_valor,
                "Semana": st.session_state.semana_nova,
                "DataHora": pd.Timestamp.now()
            })

# Atualiza estado de edições
if edicoes:
    st.session_state.edicoes = edicoes
    st.session_state.has_unsaved_changes = True

# ============================
# Persistência (I/O só aqui)
# ============================
salvar_col1, salvar_col2 = st.columns([1, 3])
with salvar_col1:
    can_save = st.session_state.has_unsaved_changes and len(st.session_state.edicoes) > 0
    if st.button("Salvar todas as alterações da semana ativa", disabled=not can_save):
        try:
            # aplica em memória
            for ed in st.session_state.edicoes:
                idx = ed["index"]
                col = ed["Mês"]
                val = ed["Novo Valor"]
                if idx in df_semana.index and col in df_semana.columns:
                    df_semana.at[idx, col] = val

            # 🔒 só salva Moderado
            df_final = _filtrar_moderado(df_semana.copy())
            salvar_base_dados(df_final)

            # histórico
            salvar_em_aba(pd.DataFrame(st.session_state.edicoes), aba="Histórico")

            # limpa estado
            st.session_state.df_previsto = df_final
            st.session_state.edicoes = []
            st.session_state.has_unsaved_changes = False

            # atualiza caches
            st.session_state.df_semana_cached = preparar_df_semana(st.session_state.df_previsto)
            st.session_state.df_semana_cache_key = (id(st.session_state.df_previsto), st.session_state.semana_nova)

            st.success("Alterações salvas com sucesso (somente Moderado).")
        except Exception as e:
            st.error("Erro ao salvar as alterações.")
            st.exception(e)

with salvar_col2:
    if st.session_state.has_unsaved_changes:
        st.info("Há alterações pendentes. Salve para confirmar.")
    else:
        st.success("Sem alterações pendentes.")

# ============================
# Rodapé: tempo total
# ============================
elapsed_total = time.time() - _start_total
st.sidebar.info(f"Tempo de execução desta interação: {elapsed_total:.2f}s")

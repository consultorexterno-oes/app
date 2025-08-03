import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from entrada_saida.funcoes_io import carregar_previsto
from api.graph_api import carregar_meses_permitidos

# ============================
# Configuração de Cores
# ============================
bg_color = "#FFFFFF"
fg_color = "#000000"
accent_color = "#033347"
paleta_graficos = ["#033347", "#E2725B", "#4CAF50", "#2196F3"]

# ============================
# Configuração da página
# ============================
st.set_page_config(page_title="Análises", layout="wide")

# CSS customizado
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
    </style>
    """,
    unsafe_allow_html=True
)

# ============================
# Login simples
# ============================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("🔐 Acesso restrito")
    senha = st.text_input("Digite a senha para entrar:", type="password")

    if senha == "Narota27":
        st.session_state.autenticado = True
        st.success("✅ Acesso liberado! Aguarde o carregamento do sistema...")
        st.rerun()
    elif senha != "":
        st.error("❌ Senha incorreta.")
    st.stop()

# ============================
# Carregar dados
# ============================
if "df_previsto" not in st.session_state:
    try:
        with st.spinner("📊 Carregando dados para análise..."):
            st.session_state.df_previsto = carregar_previsto(None)
            st.session_state.meses_permitidos = carregar_meses_permitidos()
    except Exception as e:
        st.error("Erro ao carregar os dados para análise.")
        st.exception(e)
        st.stop()

df = st.session_state.df_previsto
meses_permitidos_admin = st.session_state.get("meses_permitidos", [])

# ============================
# Filtros
# ============================
st.sidebar.subheader("🔍 Filtros de Análise")

# Filtros hierárquicos
gerencia = st.sidebar.selectbox("Gerência", options=df["Gerência"].dropna().unique())
complexo = st.sidebar.selectbox("Complexo", options=df[df["Gerência"] == gerencia]["Complexo"].dropna().unique())
area = st.sidebar.selectbox("Área", options=df[(df["Gerência"] == gerencia) & (df["Complexo"] == complexo)]["Área"].dropna().unique())
classificacao = st.sidebar.selectbox("Classificação", options=df["Classificação"].dropna().unique())
cenario = st.sidebar.selectbox("Cenário", options=df["Cenário"].dropna().unique())

# Seleção de semanas
todas_semanas = sorted(df["Revisão"].dropna().unique())
semanas_selecionadas = st.sidebar.multiselect(
    "Selecione as semanas para comparar",
    options=todas_semanas,
    default=todas_semanas[-2:] if len(todas_semanas) >= 2 else todas_semanas
)

# Seleção de indicadores
OPCOES_AGREGADAS = [
    "Receita Bruta Total",
    "Impostos sobre Receita",
    "Custo Total",
    "Lucro Bruto (MC)"
]

analises_selecionadas = st.sidebar.multiselect(
    "Selecione as análises (indicadores agregados)",
    options=OPCOES_AGREGADAS,
    default=["Receita Bruta Total"]
)

if not analises_selecionadas:
    st.warning("⚠️ Selecione pelo menos um indicador.")
    st.stop()

# Seleção de meses
colunas_meses = [
    col for col in df.columns
    if pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]

if meses_permitidos_admin:
    meses_disponiveis = [m for m in colunas_meses if m in meses_permitidos_admin]
else:
    meses_disponiveis = colunas_meses

meses_selecionados = st.sidebar.multiselect(
    "Selecione os meses para análise",
    options=meses_disponiveis,
    default=meses_disponiveis[:3] if meses_disponiveis else []
)

# ============================
# Filtrar dados
# ============================
df_filtrado = df[
    (df["Revisão"].isin(semanas_selecionadas)) &
    (df["Gerência"] == gerencia) &
    (df["Complexo"] == complexo) &
    (df["Área"] == area) &
    (df["Classificação"] == classificacao) &
    (df["Cenário"] == cenario)
]

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados")
    st.stop()

# Somente meses selecionados
df_valores = df_filtrado[["Revisão"] + meses_selecionados].copy()

# Converter valores para numérico e somar
df_valores[meses_selecionados] = df_valores[meses_selecionados].apply(pd.to_numeric, errors="coerce").fillna(0)

# Agrupar por semana e somar
df_agrupado = df_valores.groupby("Revisão")[meses_selecionados].sum()

# Totalizar meses para cada semana
df_agrupado["Total"] = df_agrupado.sum(axis=1)

# ============================
# Plot - Comparativo por Análise
# ============================
tab1, tab2, tab3 = st.tabs(["Comparativo por Análise", "Comparativo por Mês", "Dados Detalhados"])

with tab1:
    st.subheader(f"Comparativo - {gerencia} > {complexo} > {area}")

    dados_plot = df_agrupado.reset_index()

    fig = px.bar(
        dados_plot,
        x="Revisão",
        y="Total",
        text_auto=True,
        color_discrete_sequence=paleta_graficos,
        title=f"Comparativo de {', '.join(analises_selecionadas)} (Meses selecionados: {len(meses_selecionados)})"
    )
    fig.update_traces(texttemplate="R$ %{y:,.2f}")
    fig.update_layout(yaxis_title="Valor Total (R$)")

    st.plotly_chart(fig, use_container_width=True)

# ============================
# Plot - Comparativo por Mês
# ============================
with tab2:
    st.subheader(f"Evolução Mensal - {gerencia} > {complexo} > {area}")

    df_mes = df_valores.melt(id_vars=["Revisão"], var_name="Mês", value_name="Valor")
    df_mes["Mês"] = pd.to_datetime(df_mes["Mês"], dayfirst=True).dt.strftime("%b/%Y")

    fig2 = px.bar(
        df_mes,
        x="Mês",
        y="Valor",
        color="Revisão",
        barmode="group",
        color_discrete_sequence=paleta_graficos,
        title="Evolução Mensal por Semana"
    )
    fig2.update_traces(texttemplate="R$ %{y:,.2f}")
    fig2.update_layout(yaxis_title="Valor (R$)")

    st.plotly_chart(fig2, use_container_width=True)

# ============================
# Tab - Dados Detalhados
# ============================
with tab3:
    st.subheader("Dados Detalhados")
    st.dataframe(df_filtrado, use_container_width=True, height=600)

# Botão recarregar
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    for key in ["df_previsto", "meses_permitidos"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

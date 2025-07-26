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
# Configuração de Cores (Manual)
# ============================
bg_color = "#FFFFFF"  # Cor de fundo
fg_color = "#000000"  # Cor do texto
accent_color = "#033347"  # Cor de destaque
paleta_graficos = ["#033347", "#E2725B", "#4CAF50", "#2196F3"]  # Paleta de cores para gráficos

# ============================
# Configuração da página
# ============================
st.set_page_config(page_title="Análises", layout="wide")

# Aplicar CSS com tema
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

# Exibir logo
st.image("assets/Logo Rota 27.png", width=400)
st.subheader("📈 Análise Comparativa entre Semanas")

# --- Tela de login simples ---
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

# --- Carregar dados ---
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

# --- Filtros ---
VALORES_ANALISE = [
    "RECEITA MAO DE OBRA",
    "RECEITA LOCAÇÃO",
    "RECEITA DE INDENIZAÇÃO",
    "CUSTO COM MAO DE OBRA",
    "CUSTO COM INSUMOS",
    "LOCAÇÃO DE EQUIPAMENTOS"
]

st.sidebar.subheader("🔍 Filtros de Análise")

# Filtros hierárquicos
gerencias_disponiveis = df["Gerência"].dropna().unique()
gerencia_selecionada = st.sidebar.selectbox("Gerência", options=gerencias_disponiveis)

complexos_disponiveis = df[df["Gerência"] == gerencia_selecionada]["Complexo"].dropna().unique()
complexo_selecionado = st.sidebar.selectbox("Complexo", options=complexos_disponiveis)

areas_disponiveis = df[
    (df["Gerência"] == gerencia_selecionada) &
    (df["Complexo"] == complexo_selecionado)
]["Área"].dropna().unique()
area_selecionada = st.sidebar.selectbox("Área", options=areas_disponiveis)

# Novos filtros
classificacoes_disponiveis = df["Classificação"].dropna().unique()
classificacao_selecionada = st.sidebar.selectbox("Classificação", options=classificacoes_disponiveis)

cenarios_disponiveis = df["Cenário"].dropna().unique()
cenario_selecionado = st.sidebar.selectbox("Cenário", options=cenarios_disponiveis)

# Seleção de semanas
todas_semanas = sorted(df["Revisão"].dropna().unique())
semanas_selecionadas = st.sidebar.multiselect(
    "Selecione as semanas para comparar",
    options=todas_semanas,
    default=todas_semanas[-2:] if len(todas_semanas) >= 2 else todas_semanas
)

# Seleção de análises
analises_selecionadas = st.sidebar.multiselect(
    "Selecione as análises",
    options=VALORES_ANALISE,
    default=VALORES_ANALISE
)

# Seleção de meses
colunas_meses = [
    col for col in df.columns
    if pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]
if meses_permitidos_admin:
    meses_disponiveis = [m for m in colunas_meses if m in meses_permitidos_admin]
    st.sidebar.info(f"{len(meses_disponiveis)} meses disponíveis para edição")
else:
    meses_disponiveis = colunas_meses
    st.sidebar.warning("Todos os meses disponíveis (nenhum filtro aplicado)")

meses_selecionados = st.sidebar.multiselect(
    "Selecione os meses para análise",
    options=meses_disponiveis,
    default=meses_disponiveis[:3] if meses_disponiveis else []
)

# --- Processamento ---
df_filtrado = df[
    (df["Revisão"].isin(semanas_selecionadas)) &
    (df["Análise de emissão"].isin(analises_selecionadas)) &
    (df["Gerência"] == gerencia_selecionada) &
    (df["Complexo"] == complexo_selecionado) &
    (df["Área"] == area_selecionada) &
    (df["Classificação"] == classificacao_selecionada) &
    (df["Cenário"] == cenario_selecionado)
]

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados")
    st.stop()

# --- Gráficos ---
tab1, tab2, tab3 = st.tabs(["Comparativo por Análise", "Comparativo por Mês", "Dados Detalhados"])

with tab1:
    st.subheader(f"Comparativo por Tipo de Análise - {gerencia_selecionada} > {complexo_selecionado} > {area_selecionada}")
    
    if not meses_selecionados:
        st.warning("Selecione pelo menos um mês para análise")
    else:
        df_agrupado = df_filtrado.groupby(["Revisão", "Análise de emissão"])[meses_selecionados].sum().reset_index()
        df_agrupado["Total"] = df_agrupado[meses_selecionados].sum(axis=1)

        # Calcular delta (diferença entre semana mais nova e mais antiga)
        if len(semanas_selecionadas) >= 2:
            semana_antiga = semanas_selecionadas[0]
            semana_nova = semanas_selecionadas[-1]
            df_pivot = df_agrupado.pivot(index="Análise de emissão", columns="Revisão", values="Total").fillna(0)
            df_pivot["Delta"] = df_pivot.get(semana_nova, 0) - df_pivot.get(semana_antiga, 0)
            df_agrupado = df_agrupado.merge(df_pivot["Delta"].reset_index(), on="Análise de emissão", how="left")
        else:
            df_agrupado["Delta"] = 0

        # Gráfico
        fig1 = px.bar(
            df_agrupado,
            x="Análise de emissão",
            y="Total",
            color="Revisão",
            barmode="group",
            text_auto=True,
            height=500,
            title=f"Total por Análise (Meses selecionados: {len(meses_selecionados)})",
            color_discrete_sequence=paleta_graficos
        )

        # Tooltip: valor + delta
        fig1.update_traces(
            texttemplate="R$ %{y:,.2f}",
            hovertemplate="<b>%{x}</b><br>Valor: R$ %{y:,.2f}<br>Delta (nova - antiga): R$ %{customdata:,.2f}<extra></extra>",
            customdata=df_agrupado["Delta"]
        )

        fig1.update_layout(
            xaxis_title="Tipo de Análise",
            yaxis_title="Valor Total (R$)",
            legend_title="Semana",
            yaxis_tickformat=","
        )

        st.plotly_chart(fig1, use_container_width=True)

with tab2:
    st.subheader(f"Comparativo por Mês - {gerencia_selecionada} > {complexo_selecionado} > {area_selecionada}")
    st.info("""
    Esta visualização mostra a evolução dos valores mês a mês para cada tipo de análise,
    comparando as semanas selecionadas. Cada gráfico representa um tipo de análise diferente.
    """)
    
    if not meses_selecionados:
        st.warning("Selecione pelo menos um mês para visualizar este gráfico")
    else:
        df_melted = df_filtrado.melt(
            id_vars=["Revisão", "Análise de emissão"],
            value_vars=meses_selecionados,
            var_name="Mês",
            value_name="Valor"
        )
        df_melted["Mês"] = pd.to_datetime(df_melted["Mês"], dayfirst=True)
        df_melted["Mês Formatado"] = df_melted["Mês"].dt.strftime("%b/%Y")
        
        fig2 = px.bar(
            df_melted,
            x="Mês Formatado",
            y="Valor",
            color="Revisão",
            facet_col="Análise de emissão",
            facet_col_wrap=2,
            barmode="group",
            height=800,
            title="Evolução Mensal por Tipo de Análise",
            labels={"Mês Formatado": "Mês", "Valor": "Valor (R$)"},
            color_discrete_sequence=paleta_graficos
        )

        fig2.update_traces(
            texttemplate="R$ %{y:,.2f}",
            hovertemplate="R$ %{y:,.2f}<extra></extra>"
        )
        fig2.update_layout(
            hovermode="x unified",
            yaxis_title="Valor (R$)",
            yaxis_tickformat=","
        )

        st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader(f"Dados Detalhados - {gerencia_selecionada} > {complexo_selecionado} > {area_selecionada}")
    st.dataframe(
        df_filtrado.sort_values(["Revisão", "Análise de emissão"]),
        use_container_width=True,
        height=600
    )

# Botão recarregar dados
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    if "df_previsto" in st.session_state:
        del st.session_state["df_previsto"]
    if "meses_permitidos" in st.session_state:
        del st.session_state["meses_permitidos"]
    st.rerun()

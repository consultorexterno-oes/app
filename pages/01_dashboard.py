import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from entrada_saida.funcoes_io import carregar_previsto
from api.graph_api import carregar_meses_permitidos
from transformacao.funcoes_auxiliares import calcular_todos_indicadores

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

# ============================
# Filtros de Análise
# ============================
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

# Opções de indicadores agregados
OPCOES_AGREGADAS = [
    "Receita Bruta Total",
    "Impostos sobre Receita",
    "Custo Total",
    "Lucro Bruto (MC)"
]

analises_selecionadas = st.sidebar.multiselect(
    "Selecione as análises (indicadores agregados)",
    options=OPCOES_AGREGADAS,
    default=["Receita Bruta Total", "Lucro Bruto (MC)"]
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

# ============================
# Processamento dos indicadores
# ============================
df_filtrado = df[
    (df["Revisão"].isin(semanas_selecionadas)) &
    (df["Gerência"] == gerencia_selecionada) &
    (df["Complexo"] == complexo_selecionado) &
    (df["Área"] == area_selecionada) &
    (df["Classificação"] == classificacao_selecionada) &
    (df["Cenário"] == cenario_selecionado)
]

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados")
    st.stop()

# Calcula todos indicadores agregados
indicadores = calcular_todos_indicadores(df_filtrado)

# Filtra apenas os indicadores escolhidos pelo usuário
dados_plot = pd.DataFrame([
    {"Indicador": nome, "Valor": indicadores[nome + " (R$)"]}
    for nome in analises_selecionadas
])

# ============================
# Gráficos
# ============================
tab1, tab2, tab3 = st.tabs(["Comparativo por Análise", "Comparativo por Mês", "Dados Detalhados"])

# --- TAB 1: Comparativo por Análise ---
with tab1:
    st.subheader(f"Comparativo por Indicadores - {gerencia_selecionada} > {complexo_selecionado} > {area_selecionada}")

    if not meses_selecionados:
        st.warning("Selecione pelo menos um mês para análise")
    else:
        # Apenas gráfico com os indicadores agregados selecionados
        fig1 = px.bar(
            dados_plot,
            x="Indicador",
            y="Valor",
            text_auto=True,
            height=500,
            color_discrete_sequence=paleta_graficos,
            title=f"Indicadores agregados (Meses selecionados: {len(meses_selecionados)})"
        )
        fig1.update_traces(
            texttemplate="R$ %{y:,.2f}",
            hovertemplate="Indicador: %{x}<br>Valor: R$ %{y:,.2f}<extra></extra>"
        )
        fig1.update_layout(
            xaxis_title="Indicador",
            yaxis_title="Valor Total (R$)",
            yaxis_tickformat=","
        )

        st.plotly_chart(fig1, use_container_width=True)

# --- TAB 2: Comparativo por Mês ---
with tab2:
    st.subheader(f"Evolução Mensal por Indicadores - {gerencia_selecionada} > {complexo_selecionado} > {area_selecionada}")
    st.info("""
    Evolução mês a mês dos valores dos indicadores agregados selecionados.
    """)

    if not meses_selecionados:
        st.warning("Selecione pelo menos um mês para visualizar este gráfico")
    else:
        # Montar DataFrame mensal com os indicadores agregados
        df_mes = []
        for indicador in analises_selecionadas:
            valor = indicadores[indicador + " (R$)"]
            for mes in meses_selecionados:
                df_mes.append({
                    "Indicador": indicador,
                    "Mês": pd.to_datetime(mes, dayfirst=True).strftime("%b/%Y"),
                    "Valor": valor
                })
        df_mes = pd.DataFrame(df_mes)

        fig2 = px.bar(
            df_mes,
            x="Mês",
            y="Valor",
            color="Indicador",
            barmode="group",
            height=800,
            color_discrete_sequence=paleta_graficos,
            title="Evolução Mensal dos Indicadores"
        )
        fig2.update_traces(
            texttemplate="R$ %{y:,.2f}",
            hovertemplate="Mês: %{x}<br>Indicador: %{color}<br>Valor: R$ %{y:,.2f}<extra></extra>"
        )
        fig2.update_layout(
            hovermode="x unified",
            yaxis_title="Valor (R$)",
            yaxis_tickformat=","
        )

        st.plotly_chart(fig2, use_container_width=True)

# --- TAB 3: Dados Detalhados ---
with tab3:
    st.subheader(f"Dados Detalhados - {gerencia_selecionada} > {complexo_selecionado} > {area_selecionada}")
    st.dataframe(
        df_filtrado.sort_values(["Revisão"]),
        use_container_width=True,
        height=600
    )

# --- Botão recarregar ---
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    if "df_previsto" in st.session_state:
        del st.session_state["df_previsto"]
    if "meses_permitidos" in st.session_state:
        del st.session_state["meses_permitidos"]
    st.rerun()

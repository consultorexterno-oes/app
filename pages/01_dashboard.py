import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
from datetime import datetime, timedelta
import calendar

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Importações (mantidas do código original)
from entrada_saida.funcoes_io import carregar_previsto
from api.graph_api import carregar_meses_permitidos

# ============================
# Configuração de Cores
# ============================
bg_color = "#FFFFFF"
fg_color = "#000000"
accent_color = "#033347"
secondary_color = "#E2725B"
positive_color = "#4CAF50"
negative_color = "#F44336"
paleta_graficos = ["#033347", "#E2725B", "#4CAF50", "#2196F3", "#FFC107", "#9C27B0"]

st.set_page_config(
    page_title="Dashboard de Análise Financeira", 
    layout="wide",
    page_icon="📊"
)

# ============================
# CSS customizado
# ============================
st.markdown(
    f"""
    <style>
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
    .metric-card {{
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid {accent_color};
        margin-bottom: 15px;
    }}
    .week-value {{
        font-size: 14px;
        margin: 5px 0;
    }}
    .delta-positive {{
        color: {positive_color};
        font-weight: bold;
    }}
    .delta-negative {{
        color: {negative_color};
        font-weight: bold;
    }}
    .highlight {{
        color: {accent_color};
        font-weight: bold;
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
    st.title("🔐 Acesso ao Dashboard Financeiro")
    senha = st.text_input("Digite a senha para entrar:", type="password")
    
    if senha == "Narota27":
        st.session_state.autenticado = True
        st.success("✅ Acesso liberado!")
        st.rerun()
    elif senha != "":
        st.error("❌ Senha incorreta.")
        st.stop()

# ============================
# Carregar dados
# ============================
@st.cache_data(ttl=3600)  # Cache por 1 hora
def carregar_dados():
    with st.spinner("📊 Carregando dados para análise..."):
        df_previsto = carregar_previsto(None)
        meses_permitidos = carregar_meses_permitidos()
        return df_previsto, meses_permitidos

if "df_previsto" not in st.session_state:
    st.session_state.df_previsto, st.session_state.meses_permitidos = carregar_dados()

df = st.session_state.df_previsto.copy()
meses_permitidos_admin = st.session_state.get("meses_permitidos", [])

# 🔒 Só usa Cenário Moderado
if "Cenário" in df.columns:
    df = df[df["Cenário"].str.casefold() == "moderado"]

# ============================
# Funções auxiliares
# ============================
def formatar_moeda(valor):
    """Formata valor como moeda brasileira"""
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_delta(valor):
    """Formata valor delta com sinal"""
    if pd.isna(valor) or valor == 0:
        return "R$ 0,00"
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{formatar_moeda(valor)}"

def obter_valores_por_semana(df_valores, meses_selecionados):
    """Obtém os valores por semana para cada mês"""
    valores_por_mes = {}
    
    for mes in meses_selecionados:
        if mes in df_valores.columns:
            valores_por_mes[mes] = {}
            for _, row in df_valores.iterrows():
                semana = row['Revisão']
                valor = row[mes]
                valores_por_mes[mes][semana] = valor
    
    return valores_por_mes

def calcular_deltas_semanas(df_valores, meses_selecionados):
    """Calcula os deltas entre semanas consecutivas"""
    deltas_por_mes = {}
    
    # Ordenar semanas
    semanas_ordenadas = sorted(df_valores['Revisão'].unique())
    
    for mes in meses_selecionados:
        if mes in df_valores.columns:
            deltas_por_mes[mes] = {}
            
            for i in range(1, len(semanas_ordenadas)):
                semana_atual = semanas_ordenadas[i]
                semana_anterior = semanas_ordenadas[i-1]
                
                valor_atual = df_valores[df_valores['Revisão'] == semana_atual][mes].values[0]
                valor_anterior = df_valores[df_valores['Revisão'] == semana_anterior][mes].values[0]
                
                delta = valor_atual - valor_anterior
                deltas_por_mes[mes][f"{semana_anterior} → {semana_atual}"] = delta
    
    return deltas_por_mes

def criar_grafico_delta_mensal(deltas_por_mes):
    """Cria gráfico de deltas entre semanas"""
    # Preparar dados para o gráfico
    dados_grafico = []
    for mes, deltas in deltas_por_mes.items():
        mes_formatado = pd.to_datetime(mes, dayfirst=True).strftime("%b/%Y")
        for comparacao, delta in deltas.items():
            dados_grafico.append({
                'Mês': mes_formatado,
                'Comparação': comparacao,
                'Delta': delta
            })
    
    if not dados_grafico:
        return None
    
    df_delta = pd.DataFrame(dados_grafico)
    
    fig = px.bar(
        df_delta,
        x="Mês",
        y="Delta",
        color="Comparação",
        barmode="group",
        title="Variação entre Semanas (Delta)",
        color_discrete_sequence=paleta_graficos
    )
    
    fig.update_traces(
        texttemplate="%{y:+,.2f}",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{customdata}<br>Delta: %{y:+,.2f}<extra></extra>",
        customdata=df_delta['Comparação']
    )
    
    fig.update_layout(
        yaxis_title="Variação (R$)",
        xaxis_title="Mês",
        hovermode="closest"
    )
    
    # Adicionar linha horizontal em y=0
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.7)
    
    return fig

def criar_grafico_evolucao_mensal(df_mes, meses_formatados):
    """Cria gráfico de evolução mensal"""
    fig = px.line(
        df_mes, 
        x="Mês", 
        y="Valor", 
        color="Revisão",
        markers=True,
        title="Evolução Mensal por Semana",
        color_discrete_sequence=paleta_graficos
    )
    
    # Adicionar barras para melhor visualização
    for i, revisao in enumerate(df_mes['Revisão'].unique()):
        df_temp = df_mes[df_mes['Revisão'] == revisao]
        fig.add_trace(go.Bar(
            x=df_temp['Mês'],
            y=df_temp['Valor'],
            name=revisao,
            opacity=0.3,
            marker_color=paleta_graficos[i % len(paleta_graficos)],
            showlegend=False
        ))
    
    fig.update_layout(
        yaxis_title="Valor (R$)",
        xaxis_title="Mês",
        hovermode="x unified"
    )
    fig.update_traces(hovertemplate="R$ %{y:,.2f}")
    
    return fig

def criar_grafico_comparativo_semanas(df_valores, meses_selecionados):
    """Cria gráfico comparativo entre semanas"""
    fig = go.Figure()
    
    for i, semana in enumerate(df_valores['Revisão'].unique()):
        valores = df_valores[df_valores['Revisão'] == semana][meses_selecionados].sum(axis=1).values
        fig.add_trace(go.Bar(
            x=[semana],
            y=valores,
            name=semana,
            marker_color=paleta_graficos[i % len(paleta_graficos)],
            text=[formatar_moeda(sum(valores))],
            textposition='auto'
        ))
    
    fig.update_layout(
        title="Comparativo entre Semanas (Valor Total)",
        yaxis_title="Valor Total (R$)",
        xaxis_title="Semana",
        showlegend=False
    )
    
    return fig

def criar_visualizacao_anual(df_anual):
    """Cria visualização para análise anual"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Evolução ao Longo do Ano", 
            "Distribuição por Mês",
            "Comparativo entre Meses",
            "Variação Percentual Mensal"
        ),
        specs=[
            [{"type": "scatter"}, {"type": "box"}],
            [{"type": "bar"}, {"type": "scatter"}]
        ]
    )
    
    # Gráfico 1: Evolução
    for i, revisao in enumerate(df_anual['Revisão'].unique()):
        df_temp = df_anual[df_anual['Revisão'] == revisao]
        fig.add_trace(
            go.Scatter(
                x=df_temp['Mês'], 
                y=df_temp['Valor'], 
                name=revisao,
                line=dict(color=paleta_graficos[i % len(paleta_graficos)])
            ),
            row=1, col=1
        )
    
    # Gráfico 2: Distribuição
    for i, mes in enumerate(df_anual['Mês'].unique()):
        df_temp = df_anual[df_anual['Mês'] == mes]
        fig.add_trace(
            go.Box(
                y=df_temp['Valor'], 
                name=mes,
                marker_color=paleta_graficos[i % len(paleta_graficos)]
            ),
            row=1, col=2
        )
    
    # Gráfico 3: Comparativo
    medias_mensais = df_anual.groupby('Mês')['Valor'].mean().reset_index()
    fig.add_trace(
        go.Bar(
            x=medias_mensais['Mês'],
            y=medias_mensais['Valor'],
            marker_color=accent_color
        ),
        row=2, col=1
    )
    
    # Gráfico 4: Variação percentual
    medias_mensais['Variacao'] = medias_mensais['Valor'].pct_change() * 100
    fig.add_trace(
        go.Scatter(
            x=medias_mensais['Mês'],
            y=medias_mensais['Variacao'],
            mode='lines+markers',
            name='Variação %',
            line=dict(color=secondary_color)
        ),
        row=2, col=2
    )
    
    fig.update_layout(height=800, showlegend=False)
    fig.update_yaxes(title_text="Valor (R$)", row=1, col=1)
    fig.update_yaxes(title_text="Valor (R$)", row=1, col=2)
    fig.update_yaxes(title_text="Valor Médio (R$)", row=2, col=1)
    fig.update_yaxes(title_text="Variação %", row=2, col=2)
    
    return fig

# ============================
# Interface principal
# ============================
st.title("📊 Dashboard de Análise Financeira")

# ============================
# Filtros
# ============================
st.sidebar.header("🔍 Filtros de Análise")

# Filtro de escopo de análise
escopo_analise = st.sidebar.radio(
    "Escopo da Análise:",
    ["Mensal", "Anual"],
    help="Selecione se deseja analisar um mês específico ou todo o ano"
)

gerencia = st.sidebar.selectbox("Gerência", options=df["Gerência"].dropna().unique())
complexo = st.sidebar.selectbox(
    "Complexo", 
    options=df[df["Gerência"] == gerencia]["Complexo"].dropna().unique()
)
area = st.sidebar.selectbox(
    "Área", 
    options=df[(df["Gerência"] == gerencia) & (df["Complexo"] == complexo)]["Área"].dropna().unique()
)
classificacao = st.sidebar.selectbox("Classificação", options=df["Classificação"].dropna().unique())
analise_emissao = st.sidebar.selectbox(
    "Análise de emissão", 
    options=df["Análise de emissão"].dropna().unique()
)

# Semanas disponíveis
todas_semanas = sorted(df["Revisão"].dropna().unique())
semanas_selecionadas = st.sidebar.multiselect(
    "Selecione as semanas para comparar",
    options=todas_semanas,
    default=todas_semanas[-2:] if len(todas_semanas) >= 2 else todas_semanas
)

# Meses disponíveis
colunas_meses = [
    col for col in df.columns if pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]
meses_disponiveis = [m for m in colunas_meses if not meses_permitidos_admin or m in meses_permitidos_admin]

if escopo_analise == "Mensal":
    meses_selecionados = st.sidebar.multiselect(
        "Meses para análise",
        options=meses_disponiveis,
        default=meses_disponiveis[:3] if meses_disponiveis else []
    )
else:  # Anual
    meses_selecionados = meses_disponiveis  # Todos os meses para análise anual

if not semanas_selecionadas or not meses_selecionados:
    st.warning("⚠️ Selecione ao menos uma semana e um mês.")
    st.stop()

# ============================
# Filtrar dados
# ============================
df_filtrado = df[
    (df["Revisão"].isin(semanas_selecionadas)) &
    (df["Gerência"] == gerencia) &
    (df["Complexo"] == complexo) &
    (df["Área"] == area) &
    (df["Classificação"] == classificacao) &
    (df["Análise de emissão"] == analise_emissao)
]

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados")
    st.stop()

# Mantém só os meses
df_valores = df_filtrado[["Revisão"] + meses_selecionados].copy()
df_valores[meses_selecionados] = df_valores[meses_selecionados].apply(pd.to_numeric, errors="coerce").fillna(0)

# Prepara dados para visualização
df_mes = df_valores.melt(id_vars=["Revisão"], var_name="Mês", value_name="Valor")
df_mes = df_mes[df_mes["Mês"].isin(meses_selecionados)]
df_mes["Mês"] = pd.to_datetime(df_mes["Mês"], dayfirst=True).dt.strftime("%b/%Y")

# ============================
# Obter valores por semana e calcular deltas
# ============================
valores_por_semana = obter_valores_por_semana(df_valores, meses_selecionados)
deltas_por_semana = calcular_deltas_semanas(df_valores, meses_selecionados)

# ============================
# Layout principal
# ============================
st.header(f"Análise: {gerencia} > {complexo} > {area}")
st.subheader(f"Classificação: {classificacao} | Emissão: {analise_emissao}")

# Exibir métricas resumidas
st.markdown("### 📈 Valores por Semana")

if escopo_analise == "Mensal":
    cols = st.columns(len(meses_selecionados))
    for i, mes in enumerate(meses_selecionados):
        mes_formatado = pd.to_datetime(mes, dayfirst=True).strftime("%b/%Y")
        with cols[i]:
            st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
            st.markdown(f"**{mes_formatado}**")
            
            # Mostrar valores de cada semana para este mês
            if mes in valores_por_semana:
                semanas_ordenadas = sorted(valores_por_semana[mes].keys())
                
                for j, semana in enumerate(semanas_ordenadas):
                    valor = valores_por_semana[mes][semana]
                    
                    # Mostrar valor da semana
                    st.markdown(
                        f"<div class='week-value'>{semana}: <span class='highlight'>{formatar_moeda(valor)}</span></div>", 
                        unsafe_allow_html=True
                    )
                    
                    # Mostrar delta se houver semana anterior
                    if j > 0:
                        semana_anterior = semanas_ordenadas[j-1]
                        valor_anterior = valores_por_semana[mes][semana_anterior]
                        delta = valor - valor_anterior
                        
                        classe_delta = "delta-positive" if delta >= 0 else "delta-negative"
                        st.markdown(
                            f"<div class='week-value'>Δ {semana_anterior}→{semana}: <span class='{classe_delta}'>{formatar_delta(delta)}</span></div>", 
                            unsafe_allow_html=True
                        )
            
            st.markdown("</div>", unsafe_allow_html=True)
else:
    # Para análise anual, mostrar valores por trimestre
    df_mes['Data'] = pd.to_datetime(df_mes['Mês'], format='%b/%Y')
    df_mes['Trimestre'] = df_mes['Data'].dt.quarter
    
    trimestres = {1: "1º Trimestre", 2: "2º Trimestre", 3: "3º Trimestre", 4: "4º Trimestre"}
    trimestres_data = {}
    
    for trimestre in range(1, 5):
        df_trimestre = df_mes[df_mes['Trimestre'] == trimestre]
        if not df_trimestre.empty:
            trimestres_data[trimestre] = df_trimestre
    
    cols = st.columns(min(4, len(trimestres_data)))
    
    for i, (trimestre, df_trimestre) in enumerate(trimestres_data.items()):
        if i < 4:  # Máximo de 4 trimestres
            with cols[i]:
                st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown(f"**{trimestres.get(trimestre, f'{trimestre}º Trimestre')}**")
                
                # Mostrar valores por semana para cada mês no trimestre
                meses_no_trimestre = df_trimestre['Mês'].unique()
                for mes in meses_no_trimestre:
                    st.markdown(f"**{mes}**")
                    df_mes_trimestre = df_trimestre[df_trimestre['Mês'] == mes]
                    
                    semanas_mes = sorted(df_mes_trimestre['Revisão'].unique())
                    for j, semana in enumerate(semanas_mes):
                        valor = df_mes_trimestre[df_mes_trimestre['Revisão'] == semana]['Valor'].values[0]
                        
                        # Mostrar valor da semana
                        st.markdown(
                            f"<div class='week-value'>{semana}: <span class='highlight'>{formatar_moeda(valor)}</span></div>", 
                            unsafe_allow_html=True
                        )
                        
                        # Mostrar delta se houver semana anterior
                        if j > 0:
                            semana_anterior = semanas_mes[j-1]
                            valor_anterior = df_mes_trimestre[df_mes_trimestre['Revisão'] == semana_anterior]['Valor'].values[0]
                            delta = valor - valor_anterior
                            
                            classe_delta = "delta-positive" if delta >= 0 else "delta-negative"
                            st.markdown(
                                f"<div class='week-value'>Δ {semana_anterior}→{semana}: <span class='{classe_delta}'>{formatar_delta(delta)}</span></div>", 
                                unsafe_allow_html=True
                            )
                
                st.markdown("</div>", unsafe_allow_html=True)

# ============================
# Abas de visualização
# ============================
if escopo_analise == "Mensal":
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Visão Geral", 
        "🔍 Comparativo Semanas", 
        "📈 Variação entre Semanas", 
        "📑 Dados Detalhados"
    ])
else:
    tab1, tab2, tab3 = st.tabs([
        "📊 Visão Anual", 
        "📈 Análise Detalhada", 
        "📑 Dados Completos"
    ])

# --- Visualização baseada no escopo selecionado ---
if escopo_analise == "Mensal":
    with tab1:
        st.subheader("Visão Geral - Comparativo Mensal")
        
        fig = px.bar(
            df_mes,
            x="Mês",
            y="Valor",
            color="Revisão",
            barmode="group",
            text_auto=True,
            color_discrete_sequence=paleta_graficos,
            title="Comparativo Mensal por Semana"
        )
        fig.update_traces(texttemplate="R$ %{y:,.2f}")
        fig.update_layout(yaxis_title="Valor (R$)")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Comparativo entre Semanas")
        st.plotly_chart(criar_grafico_comparativo_semanas(df_valores, meses_selecionados), use_container_width=True)
        
        # Tabela comparativa
        st.subheader("Tabela Comparativa")
        df_comparativo = df_valores.set_index('Revisão')
        st.dataframe(df_comparativo.style.format(lambda x: formatar_moeda(x)), use_container_width=True)
    
    with tab3:
        st.subheader("Variação entre Semanas (Delta)")
        
        # Gráfico de deltas
        fig_delta = criar_grafico_delta_mensal(deltas_por_semana)
        if fig_delta:
            st.plotly_chart(fig_delta, use_container_width=True)
        else:
            st.info("Não há dados suficientes para calcular variações entre semanas.")
        
        # Tabela de deltas
        st.subheader("Tabela de Variações")
        dados_delta = []
        for mes, deltas in deltas_por_semana.items():
            mes_formatado = pd.to_datetime(mes, dayfirst=True).strftime("%b/%Y")
            for comparacao, delta in deltas.items():
                dados_delta.append({
                    'Mês': mes_formatado,
                    'Comparação': comparacao,
                    'Variação': delta
                })
        
        if dados_delta:
            df_delta = pd.DataFrame(dados_delta)
            st.dataframe(
                df_delta.style.format({
                    'Variação': lambda x: formatar_delta(x)
                }), 
                use_container_width=True
            )
        else:
            st.info("Não há variações para exibir.")
    
    with tab4:
        st.subheader("Dados Detalhados")
        st.dataframe(df_valores, use_container_width=True, height=600)
        
        csv = df_valores.to_csv().encode("utf-8")
        st.download_button(
            label="⬇️ Baixar dados em CSV",
            data=csv,
            file_name="analise_mensal.csv",
            mime="text/csv"
        )

else:  # Anual
    with tab1:
        st.subheader("Visão Anual - Todos os Meses")
        st.plotly_chart(criar_visualizacao_anual(df_mes), use_container_width=True)
    
    with tab2:
        st.subheader("Análise Detalhada por Período")
        
        # Seleção de trimestre para análise detalhada
        trimestre = st.selectbox("Selecione o trimestre para análise detalhada:", [1, 2, 3, 4])
        
        df_trimestre = df_mes[df_mes['Data'].dt.quarter == trimestre]
        
        if not df_trimestre.empty:
            fig = px.bar(
                df_trimestre,
                x="Mês",
                y="Valor",
                color="Revisão",
                barmode="group",
                title=f"Análise Detalhada - {trimestre}º Trimestre"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Não há dados disponíveis para o trimestre selecionado.")
    
    with tab3:
        st.subheader("Dados Completos - Ano Todo")
        st.dataframe(df_mes, use_container_width=True, height=600)
        
        csv = df_mes.to_csv().encode("utf-8")
        st.download_button(
            label="⬇️ Baixar dados anuais em CSV",
            data=csv,
            file_name="analise_anual.csv",
            mime="text/csv"
        )

# ============================
# Recarregar
# ============================
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    for key in ["df_previsto", "meses_permitidos"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ============================
# Informações adicionais
# ============================
st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ Informações")
st.sidebar.info(
    "Este dashboard permite comparar diferentes semanas de revisão "
    "e visualizar a evolução dos valores ao longo dos meses. "
    "Use os filtros para personalizar a análise."
)
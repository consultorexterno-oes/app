import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import time
from datetime import datetime

# 1. Configurações de Path e Importações
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from entrada_saida.funcoes_io import carregar_previsto, get_version_token
from api.graph_api import carregar_semana_ativa

# Configuração da página
st.set_page_config(page_title="Dashboard O&S - Rota 27", layout="wide", page_icon="📊")

# --- CSS EXECUTIVO ---
st.markdown("""
    <style>
    :root { color-scheme: light !important; }
    .logo-container { display: flex; justify-content: flex-start; padding-bottom: 20px; }
    .filter-summary-container {
        background-color: #ffffff;
        padding: 15px 25px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 25px;
        width: 100%;
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        align-items: center;
        gap: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03);
    }
    .filter-group { display: flex; align-items: center; border-right: 2px solid #f5f5f5; padding-right: 15px; }
    .filter-group:last-child { border-right: none; }
    .filter-label { font-weight: bold; color: #E2725B; text-transform: uppercase; font-size: 0.75em; margin-right: 8px; white-space: nowrap; }
    .filter-value { color: #033347; font-size: 0.85em; font-weight: 600; }
    .section-header { background-color: #033347; color: white; padding: 12px 18px; border-radius: 8px; margin: 30px 0 15px 0; font-weight: bold; font-size: 1.1em; }
    .delta-selector-card { background-color: #fcfcfc; padding: 20px; border-radius: 12px; border: 1px solid #E2725B; margin: 20px 0; }
    </style>
""", unsafe_allow_html=True)

# --- LOGO NO TOPO ---
st.image("assets/Logo Rota 27.png", width=250)
st.markdown("---")

# --- FUNÇÃO DE FORMATAÇÃO DE DATA ---
def formatar_data_resumida(val):
    try:
        dt = pd.to_datetime(val, dayfirst=True)
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return f"{meses[dt.month-1]}/{str(dt.year)[2:]}"
    except:
        return str(val)

# 2. Lógica Mutex para Filtros
def sync_filtros(key):
    if key in st.session_state:
        escolha = st.session_state[key]
        if len(escolha) > 1 and "Todos" in escolha:
            if escolha[-1] == "Todos": st.session_state[key] = ["Todos"]
            else: st.session_state[key] = [x for x in escolha if x != "Todos"]

# 3. Carregamento de Dados
@st.cache_data(ttl=600)
def fetch_dashboard_data(token):
    df = carregar_previsto(token)
    if "Cenário" in df.columns:
        df = df[df["Cenário"].str.casefold() == "moderado"].copy()
    
    hierarquia = ["RECEITA MAO DE OBRA", "RECEITA LOCAÇÃO", "RECEITA DE INDENIZAÇÃO", "CUSTO COM MAO DE OBRA", "CUSTO COM INSUMOS", "LOCAÇÃO DE EQUIPAMENTOS"]
    df = df[df["Análise de emissão"].isin(hierarquia)].copy()
    df["Análise de emissão"] = pd.Categorical(df["Análise de emissão"], categories=hierarquia, ordered=True)
    return df.sort_values("Análise de emissão")

df_raw = fetch_dashboard_data(get_version_token())
controle = carregar_semana_ativa(version_token=get_version_token()) or {}

# 4. SIDEBAR - FILTROS
st.sidebar.title("🔍 Filtros")

op_col = ["Todos"] + sorted(df_raw["Classificação"].dropna().unique().tolist())
sel_col = st.sidebar.selectbox("Coligada", op_col)
df_f = df_raw if sel_col == "Todos" else df_raw[df_raw["Classificação"] == sel_col]

op_ger = ["Todos"] + sorted(df_f["Gerência"].dropna().unique().tolist())
sel_ger = st.sidebar.selectbox("Gerência", op_ger)
if sel_ger != "Todos": df_f = df_f[df_f["Gerência"] == sel_ger]

op_comp = ["Todos"] + sorted(df_f["Complexo"].dropna().unique().tolist())
if "d_comp" not in st.session_state: st.session_state.d_comp = ["Todos"]
st.sidebar.multiselect("Complexo", op_comp, key="d_comp", on_change=sync_filtros, args=("d_comp",))
if "Todos" not in st.session_state.d_comp: df_f = df_f[df_f["Complexo"].isin(st.session_state.d_comp)]

op_area = ["Todos"] + sorted(df_f["Área"].dropna().unique().tolist())
if "d_area" not in st.session_state: st.session_state.d_area = ["Todos"]
st.sidebar.multiselect("Área", op_area, key="d_area", on_change=sync_filtros, args=("d_area",))
if "Todos" not in st.session_state.d_area: df_f = df_f[df_f["Área"].isin(st.session_state.d_area)]

op_ana = ["Todos"] + list(df_raw["Análise de emissão"].cat.categories)
if "d_ana" not in st.session_state: st.session_state.d_ana = ["Todos"]
st.sidebar.multiselect("Análise de Emissão", op_ana, key="d_ana", on_change=sync_filtros, args=("d_ana",))
if "Todos" not in st.session_state.d_ana: df_f = df_f[df_f["Análise de emissão"].isin(st.session_state.d_ana)]

# --- FILTRO DE PERÍODO AJUSTADO (COM FORMAT_FUNC) ---
lixo = ["Revisão", "Cenário", "Semana", "Observações:", "ID", "Classificação", "Gerência", "Complexo", "Área", "Análise de emissão", "CC", "DataHora"]
todos_meses = [c for c in df_raw.columns if c not in lixo and not str(c).startswith("Unnamed") and pd.to_datetime(c, errors='coerce', dayfirst=True) is not pd.NaT]

sel_meses = st.sidebar.multiselect(
    "Período Analisado", 
    options=todos_meses, 
    default=todos_meses[:6] if len(todos_meses) >= 6 else todos_meses,
    format_func=formatar_data_resumida # AQUI APLICA O Jan/26
)

op_rev_disponiveis = sorted(df_f["Revisão"].unique(), reverse=True)
sel_rev_geral = st.sidebar.multiselect("Semanas no Dashboard", op_rev_disponiveis, default=op_rev_disponiveis[:3] if len(op_rev_disponiveis) >= 3 else op_rev_disponiveis)

if df_f.empty or not sel_rev_geral or not sel_meses:
    st.warning("⚠️ Selecione os filtros para carregar dados válidos.")
    st.stop()

# 5. PROCESSAMENTO
df_longo = df_f[df_f["Revisão"].isin(sel_rev_geral)].melt(id_vars=["Revisão"], value_vars=sel_meses, var_name="Mês", value_name="Valor")
df_longo["Valor"] = pd.to_numeric(df_longo["Valor"], errors='coerce').fillna(0)
df_agrupado = df_longo.groupby(["Mês", "Revisão"], sort=False)["Valor"].sum().reset_index()
# Formata o nome do mês para exibição no gráfico/tabela
df_agrupado["Mês Exibição"] = df_agrupado["Mês"].apply(formatar_data_resumida)
df_pivot_abs = df_agrupado.pivot(index="Mês", columns="Revisão", values="Valor")

# 6. CABEÇALHO E RESUMO
st.title("📊 Dashboard - Análises Refinado Semanal")
resumo_html = f"""
<div class="filter-summary-container">
    <div class="filter-group"><span class="filter-label">Coligada</span><span class="filter-value">{sel_col}</span></div>
    <div class="filter-group"><span class="filter-label">Gerência</span><span class="filter-value">{sel_ger}</span></div>
    <div class="filter-group"><span class="filter-label">Complexos</span><span class="filter-value">{", ".join(st.session_state.d_comp)}</span></div>
    <div class="filter-group"><span class="filter-label">Áreas</span><span class="filter-value">{", ".join(st.session_state.d_area)}</span></div>
    <div class="filter-group"><span class="filter-label">Contas</span><span class="filter-value">{", ".join(st.session_state.d_ana)}</span></div>
</div>
"""
st.markdown(resumo_html, unsafe_allow_html=True)

# 7. GRÁFICO DE BARRAS
st.markdown('<div class="section-header">📈 Comparativo de Volumes Absolutos</div>', unsafe_allow_html=True)

fig_bar = px.bar(
    df_agrupado, x="Mês Exibição", y="Valor", color="Revisão", barmode="group", text_auto='.2s',
    color_discrete_sequence=px.colors.qualitative.Bold, template="plotly_white"
)
fig_bar.update_layout(height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_bar, use_container_width=True)

# Tabela com índice formatado
df_tabela_abs = df_pivot_abs.copy()
df_tabela_abs.index = [formatar_data_resumida(i) for i in df_tabela_abs.index]
st.dataframe(df_tabela_abs[sel_rev_geral].style.format("R$ {:,.2f}"), use_container_width=True)

# 8. MONTAGEM DE DELTAS
st.markdown('<div class="section-header">⚖️ Laboratório de Variações (Montagem de Deltas)</div>', unsafe_allow_html=True)
if 'comparativos' not in st.session_state: st.session_state.comparativos = [{"id": 0}]
def adicionar_comp(): st.session_state.comparativos.append({"id": len(st.session_state.comparativos)})

for i, comp in enumerate(st.session_state.comparativos):
    col1, col2, col3 = st.columns([4, 4, 1])
    opcoes_validas = [s for s in sel_rev_geral if s in df_pivot_abs.columns]
    comp['semana_a'] = col1.selectbox(f"Par {i+1}: Semana A (Novo)", opcoes_validas, key=f"a_{i}")
    comp['semana_b'] = col2.selectbox(f"Par {i+1}: Semana B (Base)", opcoes_validas, key=f"b_{i}", index=min(1, len(opcoes_validas)-1))
    if col3.button("🗑️", key=f"del_{i}") and len(st.session_state.comparativos) > 1:
        st.session_state.comparativos.pop(i)
        st.rerun()
st.button("➕ Adicionar Novo Comparativo", on_click=adicionar_comp)

df_deltas_final = pd.DataFrame(index=df_pivot_abs.index)
for comp in st.session_state.comparativos:
    sa, sb = comp.get('semana_a'), comp.get('semana_b')
    if sa in df_pivot_abs.columns and sb in df_pivot_abs.columns:
        label = f"Δ ({sa} vs {sb})"
        df_deltas_final[label] = df_pivot_abs[sa] - df_pivot_abs[sb]

if not df_deltas_final.empty:
    df_deltas_plot = df_deltas_final.copy()
    df_deltas_plot.index = [formatar_data_resumida(i) for i in df_deltas_plot.index]
    fig_line = px.line(
        df_deltas_plot.reset_index().rename(columns={"index": "Mês"}).melt(id_vars="Mês", var_name="Comparativo", value_name="Variação"),
        x="Mês", y="Variação", color="Comparativo", markers=True, template="plotly_white"
    )
    fig_line.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_line, use_container_width=True)
    
    def color_delta(val):
        color = '#2e7d32' if val > 1 else '#d32f2f' if val < -1 else 'black'
        return f'color: {color}; font-weight: bold'
    
    df_deltas_exibicao = df_deltas_final.copy()
    df_deltas_exibicao.index = [formatar_data_resumida(i) for i in df_deltas_exibicao.index]
    st.dataframe(df_deltas_exibicao.style.format("R$ {:,.2f}").applymap(color_delta), use_container_width=True)

# 9. DETALHAMENTO FINAL
st.markdown('<div class="section-header">🔍 Detalhamento por Conta (Análise de Emissão)</div>', unsafe_allow_html=True)
semanas_vivas = list(set([c.get('semana_a') for c in st.session_state.comparativos if c.get('semana_a')] + [c.get('semana_b') for c in st.session_state.comparativos if c.get('semana_b')]))
semanas_vivas = [s for s in semanas_vivas if s in df_f["Revisão"].values]
if semanas_vivas:
    df_contas = df_f[df_f["Revisão"].isin(semanas_vivas)].groupby(["Análise de emissão", "Revisão"])[sel_meses].sum().sum(axis=1).unstack()
    st.dataframe(df_contas.style.format("R$ {:,.2f}"), use_container_width=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Sincronizar Tudo"):
    st.cache_data.clear()
    st.rerun()
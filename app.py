import streamlit as st
import pandas as pd
import time
import sys
import os
from io import BytesIO

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from configuracoes.config import COLUNAS_ID, COLUNAS_MESES
from entrada_saida.funcoes_io import (
    carregar_previsto,
    salvar_base_dados,
    salvar_em_aba,
)
from api.graph_api import carregar_semana_ativa

# ============================
# Cores fixas (sem JSON)
# ============================
bg_color = "#FFFFFF"   # Fundo branco
fg_color = "#000000"   # Texto preto
accent_color = "#033347"  # Azul escuro para botões e destaques

# ============================
# Configuração da página
# ============================
st.set_page_config(page_title="Rota 27", layout="wide")

# Forçar modo claro e aplicar cores via CSS
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

    /* Botões */
    .stButton>button {{
        background-color: {accent_color} !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.5em 1em;
    }}

    /* Hack para renomear abas do sidebar */
    section[data-testid="stSidebar"] li:nth-of-type(1) a p {{
        visibility: hidden;
        position: relative;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(1) a p::after {{
        content: 'Preencher Refinado';
        visibility: visible;
        position: absolute;
        top: 0;
        left: 0;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(2) a p {{
        visibility: hidden;
        position: relative;
    }}
    section[data-testid="stSidebar"] li:nth-of-type(2) a p::after {{
        content: 'Gerenciar Semanas';
        visibility: visible;
        position: absolute;
        top: 0;
        left: 0;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# Exibir logo
st.image("assets/Logo Rota 27.png", width=400)
st.title("Refinado Semanal - Preenchimento")

# ============================
# Autenticação simples
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
# Botão de recarregamento
# ============================
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    for key in ["df_previsto", "semana_nova", "meses_permitidos_admin"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ============================
# Carregar semana ativa
# ============================
if "semana_nova" not in st.session_state:
    try:
        semana_info = carregar_semana_ativa()
        if isinstance(semana_info, str):
            st.session_state.semana_nova = semana_info
            st.session_state.meses_permitidos_admin = []
        else:
            st.session_state.semana_nova = semana_info.get("semana", "")
            st.session_state.meses_permitidos_admin = semana_info.get("meses_permitidos", [])

        if st.session_state.semana_nova:
            st.sidebar.success(f"✳️ Semana ativa: {st.session_state.semana_nova}")
            if st.session_state.meses_permitidos_admin:
                st.sidebar.info(f"Meses permitidos: {len(st.session_state.meses_permitidos_admin)}")
        else:
            st.sidebar.warning("Nenhuma semana ativa encontrada na aba 'Controle'.")
            st.stop()
    except Exception as e:
        st.sidebar.error("Erro ao carregar a semana ativa.")
        st.exception(e)
        st.stop()
else:
    st.sidebar.success(f"✳️ Semana ativa: {st.session_state.semana_nova}")
    if st.session_state.meses_permitidos_admin:
        st.sidebar.info(f"Meses permitidos: {len(st.session_state.meses_permitidos_admin)}")

# ============================
# Carregar dados de previsão
# ============================
if "df_previsto" not in st.session_state:
    try:
        start_base = time.time()
        st.session_state.df_previsto = carregar_previsto(None)
        elapsed_base = time.time() - start_base
        st.sidebar.info(f"📅 Previsão carregada em {elapsed_base:.2f}s")
    except Exception as e:
        st.error("Erro ao carregar os dados do SharePoint.")
        st.exception(e)
        st.stop()
else:
    st.sidebar.info("📅 Usando dados do cache (clique em 'Recarregar dados' para atualizar)")

# ============================
# Lógica de edição
# ============================

VALORES_ANALISE = [
    "RECEITA MAO DE OBRA",
    "RECEITA LOCAÇÃO",
    "RECEITA DE INDENIZAÇÃO",
    "CUSTO COM MAO DE OBRA",
    "CUSTO COM INSUMOS",
    "LOCAÇÃO DE EQUIPAMENTOS"
]

# Carregar dados da semana
df_semana = st.session_state.df_previsto[
    (st.session_state.df_previsto["Revisão"] == st.session_state.semana_nova) &
    (st.session_state.df_previsto["Análise de emissão"].isin(VALORES_ANALISE))
].copy()

df_semana["Análise de emissão"] = pd.Categorical(
    df_semana["Análise de emissão"],
    categories=VALORES_ANALISE,
    ordered=True
)
df_semana = df_semana.sort_values("Análise de emissão")

if df_semana.empty:
    st.warning(f"Nenhuma linha encontrada para a semana '{st.session_state.semana_nova}'.")
    st.stop()

# Inicializar edições
if "edicoes" not in st.session_state:
    st.session_state.edicoes = []

# ============================
# Filtros para o dataframe
# ============================
st.subheader("🔎 Filtros para Visualização")

# Primeira linha com 3 filtros
col1, col2, col3 = st.columns(3)

with col1:
    # Filtro de Coligada (Classificação)
    opcoes_coligada = ["Todos"] + list(df_semana["Classificação"].dropna().unique())
    coligada_filtro = st.selectbox("Coligada", opcoes_coligada)

with col2:
    # Filtro de Gerência com opção "Todos"
    opcoes_gerencia = ["Todos"] + list(df_semana["Gerência"].dropna().unique())
    gerencia_filtro = st.selectbox("Gerência", opcoes_gerencia)

with col3:
    # Filtro de Complexo dinâmico
    if gerencia_filtro == "Todos":
        opcoes_complexo = ["Todos"] + list(df_semana["Complexo"].dropna().unique())
    else:
        opcoes_complexo = ["Todos"] + list(df_semana[df_semana["Gerência"] == gerencia_filtro]["Complexo"].dropna().unique())
    complexo_filtro = st.selectbox("Complexo", opcoes_complexo)

# Segunda linha com 2 filtros
col4, col5 = st.columns(2)

with col4:
    # Filtro de Área dinâmico
    if complexo_filtro == "Todos":
        if gerencia_filtro == "Todos":
            opcoes_area = ["Todos"] + list(df_semana["Área"].dropna().unique())
        else:
            opcoes_area = ["Todos"] + list(df_semana[df_semana["Gerência"] == gerencia_filtro]["Área"].dropna().unique())
    else:
        opcoes_area = ["Todos"] + list(df_semana[df_semana["Complexo"] == complexo_filtro]["Área"].dropna().unique())
    area_filtro = st.selectbox("Área", opcoes_area)

with col5:
    # Filtro de Análise
    opcoes_analise = ["Todos"] + [val for val in VALORES_ANALISE if val in df_semana["Análise de emissão"].unique()]
    analise_filtro = st.selectbox("Análise de emissão", opcoes_analise)

# Aplicar filtros ao dataframe
df_filtrado = df_semana.copy()

if coligada_filtro != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Classificação"] == coligada_filtro]

if gerencia_filtro != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Gerência"] == gerencia_filtro]

if complexo_filtro != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Complexo"] == complexo_filtro]

if area_filtro != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Área"] == area_filtro]

if analise_filtro != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Análise de emissão"] == analise_filtro]

# Mostrar dataframe filtrado
st.subheader(f"📄 Valores atuais filtrados para '{st.session_state.semana_nova}'")
st.dataframe(df_filtrado, use_container_width=True)

# ============================
# Seção de Edição
# ============================
st.subheader("✏️ Edição de Valores")

# Primeira linha com 3 filtros
col_edit1, col_edit2, col_edit3 = st.columns(3)

with col_edit1:
    coligada_edit = st.selectbox("Coligada para edição",
                               df_semana["Classificação"].dropna().unique(),
                               key="coligada_edit")

with col_edit2:
    gerencia_edit = st.selectbox("Gerência para edição", df_semana["Gerência"].dropna().unique(), key="gerencia_edit")

with col_edit3:
    complexo_edit = st.selectbox("Complexo para edição", 
                               df_semana[df_semana["Gerência"] == gerencia_edit]["Complexo"].dropna().unique(), 
                               key="complexo_edit")

# Segunda linha com 2 filtros
col_edit4, col_edit5 = st.columns(2)

with col_edit4:
    area_edit = st.selectbox("Área para edição", 
                           df_semana[
                               (df_semana["Gerência"] == gerencia_edit) & 
                               (df_semana["Complexo"] == complexo_edit)
                           ]["Área"].dropna().unique(),
                           key="area_edit")

with col_edit5:
    analise_edit = st.selectbox(
        "Análise de emissão para edição",
        [val for val in VALORES_ANALISE if val in df_semana["Análise de emissão"].unique()],
        key="analise_edit"
    )

# Selectbox meses (somente permitidos)
meses_todos = [
    col for col in df_semana.columns
    if col not in COLUNAS_ID + ["Observações:"] and pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]
if st.session_state.meses_permitidos_admin:
    meses_disponiveis = [m for m in meses_todos if m in st.session_state.meses_permitidos_admin]
else:
    meses_disponiveis = meses_todos

meses_display = {
    m: pd.to_datetime(m, dayfirst=True).strftime("%B %Y").capitalize()
    for m in meses_disponiveis
}

mes_edit = st.selectbox("Mês para edição", options=meses_disponiveis, format_func=lambda x: meses_display[x], key="mes_edit")

# Valor atual para edição
linhas_filtradas_edit = df_semana[
    (df_semana["Classificação"] == coligada_edit) &
    (df_semana["Gerência"] == gerencia_edit) &
    (df_semana["Complexo"] == complexo_edit) &
    (df_semana["Área"] == area_edit) &
    (df_semana["Análise de emissão"] == analise_edit)
]

valor_atual_edit = linhas_filtradas_edit[mes_edit].values[0] if not linhas_filtradas_edit.empty else 0.0
try:
    valor_atual_float_edit = float(valor_atual_edit)
except:
    valor_atual_float_edit = 0.0

novo_valor_edit = st.number_input("Novo valor para essa combinação", value=valor_atual_float_edit, step=100.0, key="novo_valor")

# Botão adicionar edição
if st.button("➕ Adicionar edição"):
    if not linhas_filtradas_edit.empty:
        for idx in linhas_filtradas_edit.index:
            st.session_state.edicoes.append({
                "index": idx,
                "Classificação": coligada_edit,
                "Gerência": gerencia_edit,
                "Complexo": complexo_edit,
                "Área": area_edit,
                "Análise de emissão": analise_edit,
                "Mês": mes_edit,
                "Novo Valor": novo_valor_edit,
                "Semana": st.session_state.semana_nova,
                "DataHora": pd.Timestamp.now()
            })
        st.success(f"{len(linhas_filtradas_edit)} edições adicionadas: {meses_display[mes_edit]} → {novo_valor_edit:.2f}")
    else:
        st.warning("⚠️ Combinação não encontrada na base.")

# Mostrar edições acumuladas
if st.session_state.edicoes:
    st.markdown("### ⌛ Edições em andamento...")
    df_edicoes = pd.DataFrame(st.session_state.edicoes)
    st.dataframe(df_edicoes, use_container_width=True)

    buffer = BytesIO()
    df_edicoes.to_excel(buffer, index=False, engine="xlsxwriter")
    st.download_button(
        label="⬇️ Baixar edições em Excel",
        data=buffer.getvalue(),
        file_name="edicoes_previstas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.button("💾 Salvar todas as alterações da semana ativa"):
        try:
            for edicao in st.session_state.edicoes:
                idx = edicao["index"]
                coluna = edicao["Mês"]
                valor = edicao["Novo Valor"]
                df_semana.at[idx, coluna] = valor

            df_antigas = st.session_state.df_previsto[
                st.session_state.df_previsto["Revisão"] != st.session_state.semana_nova
            ].copy()
            df_final = pd.concat([df_antigas, df_semana], ignore_index=True)
            salvar_base_dados(df_final)

            salvar_em_aba(df_edicoes, aba="Histórico")
            st.success("✅ Alterções salvas com sucesso!")
            st.session_state.edicoes = []
        except Exception as e:
            st.error("Erro ao salvar as alterações.")
            st.exception(e)

# --- Tempo total ---
elapsed_total = time.time() - time.time()
st.sidebar.info(f"⏱️ Tempo total: {elapsed_total:.2f} segundos")
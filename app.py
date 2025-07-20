import streamlit as st
import pandas as pd
import time
import sys
import os
from io import BytesIO

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Imports internos
from configuracoes.config import COLUNAS_ID, COLUNAS_MESES
from entrada_saida.funcoes_io import (
    carregar_previsto,
    salvar_base_dados,
    salvar_em_aba,
)
from api.graph_api import carregar_semana_ativa

# Configuração da página
st.set_page_config(page_title="Rota 27", layout="wide")
start_time_total = time.time()
st.title("📊 Refinado Semanal - O&S Gestão")

# --- Tela de login simples ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("🔐 Acesso restrito")
    senha = st.text_input("Digite a senha para entrar:", type="password")

    if senha == "Narota27":
        st.session_state.autenticado = True
        st.success("✅ Acesso liberado! Aguarde o carregamento do sistema...")
        st.experimental_rerun()
    elif senha != "":
        st.error("❌ Senha incorreta.")
    st.stop()

# --- Semana ativa definida pelo administrador ---
try:
    semana_nova = carregar_semana_ativa()
    if semana_nova:
        st.sidebar.success(f"✳️ Semana ativa: {semana_nova}")
    else:
        st.sidebar.warning("Nenhuma semana ativa encontrada na aba 'Controle'.")
        st.stop()
except Exception as e:
    st.sidebar.error("Erro ao carregar a semana ativa.")
    st.exception(e)
    st.stop()

# --- Carregamento dos dados de entrada ---
try:
    start_base = time.time()
    df_previsto = carregar_previsto(None)
    elapsed_base = time.time() - start_base
    st.sidebar.info(f"📅 Previsão carregada em {elapsed_base:.2f}s")
except Exception as e:
    st.error("Erro ao carregar os dados do SharePoint.")
    st.exception(e)
    st.stop()

# --- Filtrar apenas os dados da semana ativa ---
df_semana = df_previsto[df_previsto["Revisão"] == semana_nova].copy()
if df_semana.empty:
    st.warning(f"Nenhuma linha encontrada para a semana '{semana_nova}' na aba 'Base de Dados'.")
    st.stop()

# --- Exibir os dados atuais como referência ---
st.subheader(f"✍️ Editar valores previstos para a semana '{semana_nova}'")
st.dataframe(df_semana, use_container_width=True)

# --- Inicializar memória para edições ---
if "edicoes" not in st.session_state:
    st.session_state.edicoes = []

# --- Interface para filtros e edição guiada ---
col1, col2, col3 = st.columns(3)
with col1:
    gerencia = st.selectbox("Gerência", df_semana["Gerência"].dropna().unique())
with col2:
    complexo = st.selectbox("Complexo", df_semana[df_semana["Gerência"] == gerencia]["Complexo"].dropna().unique())
with col3:
    area = st.selectbox("Área", df_semana[
        (df_semana["Gerência"] == gerencia) & (df_semana["Complexo"] == complexo)
    ]["Área"].dropna().unique())

analise = st.selectbox(
    "Análise de emissão",
    df_semana[
        (df_semana["Gerência"] == gerencia) &
        (df_semana["Complexo"] == complexo) &
        (df_semana["Área"] == area)
    ]["Análise de emissão"].dropna().unique()
)

# --- Detectar colunas que representam meses ---
meses = [
    col for col in df_semana.columns
    if col not in COLUNAS_ID + ["Observações:"] and pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]
mes = st.selectbox("Mês", meses)

# --- Obter valor atual ---
linhas_filtradas = df_semana[
    (df_semana["Gerência"] == gerencia) &
    (df_semana["Complexo"] == complexo) &
    (df_semana["Área"] == area) &
    (df_semana["Análise de emissão"] == analise)
]

valor_atual = linhas_filtradas[mes].values[0] if not linhas_filtradas.empty else 0.0
try:
    valor_atual_float = float(valor_atual)
except:
    valor_atual_float = 0.0

novo_valor = st.number_input("Novo valor para essa combinação", value=valor_atual_float, step=100.0)

# --- Botão para adicionar edição à memória ---
if st.button("➕ Adicionar edição"):
    if not linhas_filtradas.empty:
        for idx in linhas_filtradas.index:
            st.session_state.edicoes.append({
                "index": idx,
                "Gerência": gerencia,
                "Complexo": complexo,
                "Área": area,
                "Análise de emissão": analise,
                "Mês": mes,
                "Novo Valor": novo_valor,
                "Semana": semana_nova,
                "DataHora": pd.Timestamp.now()
            })
        st.success(f"{len(linhas_filtradas)} edições adicionadas: {mes} → {novo_valor:.2f}")
    else:
        st.warning("⚠️ Combinação não encontrada na base.")

# --- Exibir edições acumuladas ---
if st.session_state.edicoes:
    st.markdown("### ✏️ Edições pendentes")
    df_edicoes = pd.DataFrame(st.session_state.edicoes)
    st.dataframe(df_edicoes, use_container_width=True)

    # Download como Excel
    buffer = BytesIO()
    df_edicoes.to_excel(buffer, index=False, engine="xlsxwriter")
    st.download_button(
        label="⬇️ Baixar edições em Excel",
        data=buffer.getvalue(),
        file_name="edicoes_previstas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Botão para salvar todas as edições ---
    if st.button("📏 Salvar todas as alterações da semana ativa"):
        try:
            for edicao in st.session_state.edicoes:
                idx = edicao["index"]
                coluna = edicao["Mês"]
                valor = edicao["Novo Valor"]
                df_semana.at[idx, coluna] = valor

            # Rejunta com base antiga e salva
            df_antigas = df_previsto[df_previsto["Revisão"] != semana_nova].copy()
            df_final = pd.concat([df_antigas, df_semana], ignore_index=True)
            salvar_base_dados(df_final)

            # Salva histórico
            salvar_em_aba(df_edicoes, aba="Histórico")

            st.success("✅ Alterações salvas com sucesso!")
            st.session_state.edicoes = []
        except Exception as e:
            st.error("Erro ao salvar as alterações.")
            st.exception(e)

# --- Tempo total de carregamento ---
elapsed_total = time.time() - start_time_total
st.sidebar.info(f"⏱️ Tempo total: {elapsed_total:.2f} segundos")

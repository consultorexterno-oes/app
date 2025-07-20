import streamlit as st
import pandas as pd
import sys
import os
import time

# Ajuste do path para importar módulos corretamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from entrada_saida.funcoes_io import (
    carregar_previsto,
    salvar_base_dados,
    gerar_semana_a_partir_revisao
)
from api.graph_api import salvar_aba_controle

st.set_page_config(page_title="Administração", layout="wide")
st.title("🔐 Painel do Administrador")

# --- Tela de login do administrador ---
if "autenticado_admin" not in st.session_state:
    st.session_state.autenticado_admin = False

if not st.session_state.autenticado_admin:
    st.subheader("🔑 Faça login para acessar os recursos e configurações do aplicativo")
    senha_admin = st.text_input("Digite a senha de administrador:", type="password")

    if senha_admin == "adm_oes":
        st.session_state.autenticado_admin = True
        st.success("✅ Acesso concedido!")
        st.rerun()
    elif senha_admin != "":
        st.error("❌ Senha incorreta.")
    st.stop()

st.subheader("🚀 Iniciando carregamento de dados...")

# --- Carrega os dados do SharePoint ---
try:
    with st.spinner("📥 Carregando aba 'Base de Dados'..."):
        inicio = time.perf_counter()
        df_base = carregar_previsto(None)
        fim = time.perf_counter()
        st.success(f"✅ Base de Dados carregada em {fim - inicio:.2f} segundos.")
except Exception as e:
    st.error("Erro ao carregar os dados do SharePoint.")
    st.exception(e)
    st.stop()

# --- Lista de revisões disponíveis na Base de Dados ---
revisoes_disponiveis = sorted(df_base["Revisão"].dropna().unique())
st.write("📌 Revisões disponíveis:", revisoes_disponiveis)

st.subheader("📌 Escolha a Revisão para duplicar")
col1, col2 = st.columns(2)

with col1:
    revisao_origem = st.selectbox("Revisão (origem dos dados)", revisoes_disponiveis)

with col2:
    nova_semana = st.text_input("Nome da nova semana", placeholder="Ex: Semana 29")

# --- Criação da nova semana ---
if st.button("➕ Criar nova semana a partir da Revisão selecionada"):
    if not nova_semana:
        st.warning("⚠️ Informe o nome da nova semana.")
        st.stop()

    if nova_semana in df_base["Revisão"].unique():
        st.error(f"A semana '{nova_semana}' já existe na aba 'Base de Dados'.")
        st.stop()

    with st.spinner(f"🔄 Gerando dados da nova semana '{nova_semana}'..."):
        inicio = time.perf_counter()
        df_nova_semana = gerar_semana_a_partir_revisao(df_base, revisao_origem, nova_semana)
        fim = time.perf_counter()
        st.success(f"✅ Nova semana gerada em {fim - inicio:.2f} segundos.")

    st.write("📊 Visualização da nova semana gerada:")
    st.dataframe(df_nova_semana)

    df_base_atualizado = pd.concat([df_base, df_nova_semana], ignore_index=True)

    try:
        with st.spinner("💾 Salvando nova semana no SharePoint..."):
            inicio = time.perf_counter()
            salvar_base_dados(df_base_atualizado)
            salvar_aba_controle(nova_semana)
            fim = time.perf_counter()
            st.success(f"✅ Semana '{nova_semana}' salva em {fim - inicio:.2f} segundos.")
            st.success("🚀 Semana definida como ativa para edição.")
    except Exception as e:
        st.error("Erro ao salvar a nova semana.")
        st.exception(e)

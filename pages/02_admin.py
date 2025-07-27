import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from entrada_saida.funcoes_io import carregar_previsto, salvar_base_dados, salvar_em_aba

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Administração", layout="wide")

# =====================================================
# ESTILOS PERSONALIZADOS
# =====================================================
st.markdown(
    """
    <style>
    :root {
        color-scheme: light !important;
    }
    body {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    [data-testid="stHeader"], [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    .stButton>button {
        background-color: #033347 !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.5em 1em;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================
# LOGO E TÍTULO
# =====================================================
st.image("assets/Logo Rota 27.png", width=300)
st.title("⚙️ Painel do Administrador do App")

# =====================================================
# AUTENTICAÇÃO SIMPLES
# =====================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("🔐 Acesso restrito")
    senha = st.text_input("Digite a senha para entrar:", type="password")

    if senha == "adm_oes":  # Senha fixa para admin
        st.session_state.autenticado = True
        st.success("✅ Acesso liberado!")
        st.experimental_rerun()
    elif senha != "":
        st.error("❌ Senha incorreta.")
    st.stop()

# =====================================================
# CARREGAR BASE DE DADOS
# =====================================================
if "df_previsto" not in st.session_state:
    try:
        with st.spinner("📊 Carregando base de dados..."):
            st.session_state.df_previsto = carregar_previsto(None)
    except Exception as e:
        st.error("Erro ao carregar a base de dados.")
        st.exception(e)
        st.stop()

df_previsto = st.session_state.df_previsto

# =====================================================
# SELECIONAR REVISÃO PARA DUPLICAR
# =====================================================
st.subheader("📌 Escolha a Revisão para duplicar")

revisoes_disponiveis = sorted(df_previsto["Revisão"].dropna().unique())
revisao_origem = st.selectbox("Revisão (origem dos dados)", revisoes_disponiveis)

nome_nova_semana = st.text_input("Nome da nova semana", placeholder="Ex: Semana 35")

# =====================================================
# SELECIONAR MESES LIBERADOS
# =====================================================
st.subheader("📅 Selecione os meses que os gerentes poderão refinar")

# Identificar colunas que são meses
colunas_meses = [
    col for col in df_previsto.columns
    if pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]

meses_selecionados = st.multiselect(
    "Meses liberados para edição",
    options=colunas_meses,
    default=colunas_meses[-6:] if len(colunas_meses) > 0 else []
)

# =====================================================
# CRIAR NOVA SEMANA
# =====================================================
if st.button("➕ Criar nova semana a partir da Revisão selecionada"):
    if not nome_nova_semana:
        st.warning("Informe o nome da nova semana antes de prosseguir.")
    else:
        try:
            # 1. Duplicar registros
            df_nova = df_previsto[df_previsto["Revisão"] == revisao_origem].copy()
            df_nova["Revisão"] = nome_nova_semana

            # 2. Salvar nova base
            df_final = pd.concat([df_previsto, df_nova], ignore_index=True)
            salvar_base_dados(df_final)

            # 3. Atualizar aba Controle (marcando nova semana como ativa)
            df_controle = pd.DataFrame({
                "Semana Ativa": [nome_nova_semana],
                "Meses Permitidos": [";".join(meses_selecionados)],
                "Data Criação": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            salvar_em_aba(df_controle, aba="Controle")

            # 4. Limpar cache para refletir nova semana no app
            st.cache_data.clear()

            st.success(
                f"Semana **{nome_nova_semana}** criada com sucesso e definida como ativa!"
            )
        except Exception as e:
            st.error("Erro ao criar a nova semana.")
            st.exception(e)

# =====================================================
# VISUALIZAR BASE ATUAL
# =====================================================
st.subheader("📋 Base de Dados Atual (visualização)")
st.dataframe(
    df_previsto.sort_values("Revisão"),
    use_container_width=True,
    height=400
)

# =====================================================
# BOTÃO DE RECARREGAR DADOS
# =====================================================
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    if "df_previsto" in st.session_state:
        del st.session_state["df_previsto"]
    st.experimental_rerun()

import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from entrada_saida.funcoes_io import carregar_previsto, salvar_base_dados, salvar_em_aba

# ============================
# Configuração da Página
# ============================
st.set_page_config(page_title="Administração", layout="wide")

# Estilos
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

# Logo e título
st.image("assets/Logo Rota 27.png", width=300)
st.title("⚙️ Painel do Administrador do App")

# ============================
# Autenticação simples
# ============================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("🔐 Acesso restrito")
    senha = st.text_input("Digite a senha para entrar:", type="password")

    if senha == "adm_oes":  # Senha fixa para admin
        st.session_state.autenticado = True
        st.success("✅ Acesso liberado!")
        st.rerun()
    elif senha != "":
        st.error("❌ Senha incorreta.")
    st.stop()

# ============================
# Carregar dados
# ============================
if "df_previsto" not in st.session_state:
    try:
        with st.spinner("📊 Carregando base de dados..."):
            st.session_state.df_previsto = carregar_previsto(None)
    except Exception as e:
        st.error("Erro ao carregar a base de dados.")
        st.exception(e)
        st.stop()

df_previsto = st.session_state.df_previsto

# ============================
# Escolher Revisão para duplicar
# ============================
st.subheader("📌 Escolha a Revisão para duplicar")

revisoes_disponiveis = sorted(df_previsto["Revisão"].dropna().unique())
revisao_origem = st.selectbox("Revisão (origem dos dados)", revisoes_disponiveis)

nome_nova_semana = st.text_input("Nome da nova semana", placeholder="Ex: Semana 29")

# ============================
# Selecionar meses permitidos
# ============================
st.subheader("📅 Selecione os meses que os gerentes poderão refinar")

# Colunas que são meses (detectadas por data)
colunas_meses = [
    col for col in df_previsto.columns
    if pd.notnull(pd.to_datetime(col, errors="coerce", dayfirst=True))
]

meses_selecionados = st.multiselect(
    "Meses liberados para edição",
    options=colunas_meses,
    default=colunas_meses[-6:]  # últimos 6 meses por padrão
)

# ============================
# Criar nova semana
# ============================
if st.button("➕ Criar nova semana a partir da Revisão selecionada"):
    if not nome_nova_semana:
        st.warning("Informe o nome da nova semana antes de prosseguir.")
    else:
        try:
            # Duplicar registros
            df_nova = df_previsto[df_previsto["Revisão"] == revisao_origem].copy()
            df_nova["Revisão"] = nome_nova_semana

            # Meses liberados (registrar em aba Controle)
            df_controle = pd.DataFrame({
                "semana": [nome_nova_semana],
                "meses_permitidos": [meses_selecionados],
                "data_criacao": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })

            # Salvar na base principal
            df_final = pd.concat([df_previsto, df_nova], ignore_index=True)
            salvar_base_dados(df_final)

            # Salvar controle
            salvar_em_aba(df_controle, aba="Controle")

            st.success(f"Semana **{nome_nova_semana}** criada com sucesso e meses liberados configurados!")
        except Exception as e:
            st.error("Erro ao criar a nova semana.")
            st.exception(e)

# ============================
# Visualizar base atual
# ============================
st.subheader("📋 Base de Dados Atual (visualização)")
st.dataframe(df_previsto.sort_values("Revisão"), use_container_width=True, height=400)

# ============================
# Botão de recarregamento
# ============================
if st.sidebar.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    if "df_previsto" in st.session_state:
        del st.session_state["df_previsto"]
    st.rerun()

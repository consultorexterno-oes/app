import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime
import time

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from entrada_saida.funcoes_io import carregar_previsto, salvar_base_dados, salvar_em_aba
from api.graph_api import baixar_aba_excel

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
    .timer {
        font-size: 0.9em;
        color: #555;
        margin-top: 5px;
    }
    .sidebar-timer {
        font-size: 0.8em;
        color: #666;
        background: #f0f0f0;
        padding: 5px;
        border-radius: 4px;
        margin-top: 10px;
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
        start_time = time.time()
        with st.spinner("📊 Carregando base de dados..."):
            st.session_state.df_previsto = carregar_previsto(None)
            load_time = time.time() - start_time
            st.markdown(f'<div class="timer">Tempo de carregamento: {load_time:.2f} segundos</div>', 
                       unsafe_allow_html=True)
    except Exception as e:
        st.error("Erro ao carregar a base de dados.")
        st.exception(e)
        st.stop()

df_previsto = st.session_state.df_previsto

# =====================================================
# CARREGAR CONTROLE PARA VER SEMANA ATIVA E HISTÓRICO
# =====================================================
try:
    df_controle = baixar_aba_excel("Controle")
except Exception:
    df_controle = pd.DataFrame(columns=["Semana Ativa", "Meses Permitidos", "semana", "meses_permitidos", "data_criacao"])

# Obter semana ativa atual
semana_ativa_atual = df_controle["Semana Ativa"].iloc[0] if not df_controle.empty else None

# =====================================================
# SELECIONAR REVISÃO PARA DUPLICAR
# =====================================================
st.subheader("📌 Escolha a Revisão para duplicar")

revisoes_disponiveis = sorted(df_previsto["Revisão"].dropna().unique())
revisao_origem = st.selectbox("Revisão (origem dos dados)", revisoes_disponiveis)

nome_nova_semana = st.text_input("Nome da nova semana", placeholder="Ex: Semana 37")

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
# CRIAR NOVA SEMANA (E DEFINIR COMO ATIVA)
# =====================================================
if st.button("➕ Criar nova semana a partir da Revisão selecionada"):
    if not nome_nova_semana:
        st.warning("Informe o nome da nova semana antes de prosseguir.")
    else:
        try:
            start_time = time.time()

            # 1. Duplicar registros
            df_nova = df_previsto[df_previsto["Revisão"] == revisao_origem].copy()
            df_nova["Revisão"] = nome_nova_semana

            # 2. Salvar nova base
            df_final = pd.concat([df_previsto, df_nova], ignore_index=True)
            salvar_base_dados(df_final)

            # 3. Atualizar aba Controle
            df_controle_novo = pd.DataFrame({
                "Semana Ativa": [nome_nova_semana],
                "Meses Permitidos": [";".join(meses_selecionados)],
                "semana": [nome_nova_semana],
                "meses_permitidos": [str(meses_selecionados)],
                "data_criacao": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            salvar_em_aba(df_controle_novo, aba="Controle")

            # 4. Limpar cache
            st.cache_data.clear()

            creation_time = time.time() - start_time
            st.success(
                f"Semana **{nome_nova_semana}** criada com sucesso e definida como ativa!"
            )
            st.markdown(f'<div class="timer">Tempo de criação: {creation_time:.2f} segundos</div>', 
                       unsafe_allow_html=True)
        except Exception as e:
            st.error("Erro ao criar a nova semana.")
            st.exception(e)

# =====================================================
# PERMITIR AO ADMIN ALTERAR SEMANA ATIVA MANUALMENTE
# =====================================================
st.subheader("🔄 Alterar Semana Ativa Manualmente")

# Listar semanas criadas (coluna 'semana' da aba Controle)
semanas_historico = df_controle["semana"].dropna().unique().tolist() if "semana" in df_controle.columns else []

if semanas_historico:
    semana_escolhida = st.selectbox(
        "Selecione a semana para ativar",
        semanas_historico,
        index=semanas_historico.index(semana_ativa_atual) if semana_ativa_atual in semanas_historico else 0
    )

    if st.button("Ativar Semana Selecionada"):
        try:
            # Atualizar aba Controle com nova semana ativa
            meses_permitidos_semana = df_controle.loc[df_controle["semana"] == semana_escolhida, "meses_permitidos"].values
            meses_formatados = meses_permitidos_semana[0] if len(meses_permitidos_semana) > 0 else ""

            df_controle_ativo = pd.DataFrame({
                "Semana Ativa": [semana_escolhida],
                "Meses Permitidos": [meses_formatados],
                "semana": [semana_escolhida],
                "meses_permitidos": [meses_formatados],
                "data_criacao": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            salvar_em_aba(df_controle_ativo, aba="Controle")

            st.cache_data.clear()
            st.success(f"Semana **{semana_escolhida}** definida como ativa!")
        except Exception as e:
            st.error("Erro ao ativar semana selecionada.")
            st.exception(e)
else:
    st.info("Nenhuma semana disponível para ativação manual.")

# =====================================================
# VISUALIZAR BASE ATUAL
# =====================================================
st.subheader("📋 Base de Dados Atual (visualização)")
start_render_time = time.time()
st.dataframe(
    df_previsto.sort_values("Revisão"),
    use_container_width=True,
    height=400
)
render_time = time.time() - start_render_time
st.markdown(f'<div class="timer">Tempo de renderização: {render_time:.2f} segundos</div>', 
           unsafe_allow_html=True)

# =====================================================
# BOTÃO DE RECARREGAR DADOS
# =====================================================
if st.sidebar.button("🔄 Recarregar dados"):
    start_reload_time = time.time()
    st.cache_data.clear()
    if "df_previsto" in st.session_state:
        del st.session_state["df_previsto"]
    reload_time = time.time() - start_reload_time
    st.sidebar.markdown(
        f'<div class="sidebar-timer">Tempo de recarregamento: {reload_time:.2f} segundos</div>',
        unsafe_allow_html=True
    )
    st.experimental_rerun()

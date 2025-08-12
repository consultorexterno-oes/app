import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime
import time

# Ajuste de path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from entrada_saida.funcoes_io import (
    carregar_previsto,
    salvar_em_aba,
    salvar_base_dados,
    bump_version_token,
    get_version_token,
)
from api.graph_api import baixar_aba_excel, salvar_apenas_aba, carregar_semana_ativa, salvar_aba_controle

# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================
st.set_page_config(page_title="Administração", layout="wide")

# =====================================================
# ESTILOS
# =====================================================
st.markdown(
    """
    <style>
    :root { color-scheme: light !important; }
    body { background-color: #ffffff !important; color: #000000 !important; }
    [data-testid="stHeader"], [data-testid="stSidebar"] {
        background-color: #ffffff !important; color: #000000 !important;
    }
    .stButton>button {
        background-color: #033347 !important; color: white !important;
        border-radius: 8px; border: none; padding: 0.5em 1em;
    }
    .timer { font-size: 0.9em; color: #555; margin-top: 5px; }
    .sidebar-timer { font-size: 0.8em; color: #666; background: #f0f0f0;
        padding: 5px; border-radius: 4px; margin-top: 10px; }
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================
# LOGO E TÍTULO
# =====================================================
st.image("assets/Logo Rota 27.png", width=300)
st.title("Painel do Administrador do App")

# =====================================================
# AUTENTICAÇÃO SIMPLES (senha fixa)
# =====================================================
if "autenticado_admin" not in st.session_state:
    st.session_state.autenticado_admin = False

if not st.session_state.autenticado_admin:
    st.subheader("Acesso restrito (Administrador)")
    password_input = st.text_input("Digite a senha de administrador:", type="password")
    if st.button("Entrar"):
        if password_input == "adm_oes":
            st.session_state.autenticado_admin = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

# =====================================================
# HELPERS
# =====================================================
def formatar_mes(mes_str: str) -> str:
    try:
        return pd.to_datetime(mes_str, dayfirst=True).strftime("%B %Y").capitalize()
    except Exception:
        return str(mes_str)

def obter_df_previsto_uma_vez() -> pd.DataFrame:
    if "df_previsto_admin" not in st.session_state:
        t0 = time.time()
        with st.spinner("Carregando base de dados..."):
            st.session_state.df_previsto_admin = carregar_previsto(get_version_token())
        st.markdown(
            f'<div class="timer">Tempo de carregamento: {time.time() - t0:.2f} s</div>',
            unsafe_allow_html=True
        )
    return st.session_state.df_previsto_admin

# =====================================================
# CARREGAR BASE DE DADOS (1x por sessão)
# =====================================================
df_previsto = obter_df_previsto_uma_vez()

# =====================================================
# CARREGAR CONTROLE (apenas leitura, 1x por sessão por token)
# =====================================================
dados_controle = carregar_semana_ativa(version_token=get_version_token()) or {}
semana_ativa_atual = dados_controle.get("semana")
meses_permitidos_atuais = dados_controle.get("meses_permitidos", [])

# =====================================================
# SELECIONAR REVISÃO PARA DUPLICAR
# =====================================================
st.subheader("Criar nova semana a partir de uma Revisão existente")

revisoes_disponiveis = sorted(df_previsto["Revisão"].dropna().unique().tolist())
revisao_origem = st.selectbox("Revisão (origem dos dados)", revisoes_disponiveis)

nome_nova_semana = st.text_input("Nome da nova semana", placeholder="Ex: Semana 37")

# Colunas de meses (precomputadas uma vez)
if "admin_colunas_meses" not in st.session_state:
    st.session_state.admin_colunas_meses = [
        c for c in df_previsto.columns
        if pd.notnull(pd.to_datetime(c, errors="coerce", dayfirst=True))
    ]

colunas_meses = st.session_state.admin_colunas_meses

meses_selecionados = st.multiselect(
    "Meses liberados para edição",
    options=colunas_meses,
    default=colunas_meses[-6:] if len(colunas_meses) > 0 else [],
    format_func=formatar_mes
)

# =====================================================
# CRIAR NOVA SEMANA (APPEND INCREMENTAL) + ATIVAR
# =====================================================
if st.button("Criar nova semana e ativar"):
    if not nome_nova_semana:
        st.warning("Informe o nome da nova semana.")
    elif nome_nova_semana in revisoes_disponiveis:
        st.warning("Esta semana já existe na base.")
    else:
        try:
            t_total = time.time()
            st.info("Iniciando criação e ativação da nova semana...")

            # 1) Duplicação em memória
            t = time.time()
            df_nova = df_previsto[df_previsto["Revisão"] == revisao_origem].copy()
            if df_nova.empty:
                st.error("Revisão de origem sem linhas na base.")
                st.stop()
            df_nova["Revisão"] = nome_nova_semana
            tempo_dup = time.time() - t

            # 2) Persistir de forma incremental (append)
            t = time.time()
            salvar_base_dados(df_nova, append=True)
            tempo_salvar_base = time.time() - t

            # 3) Atualizar Controle sobrescrevendo com única linha
            t = time.time()
            df_controle_novo = pd.DataFrame({
                "Semana Ativa": [nome_nova_semana],
                "Meses Permitidos": [";".join(meses_selecionados)],
            })
            salvar_apenas_aba("Controle", df_controle_novo)
            tempo_controle = time.time() - t

            # 4) Atualizar estado local sem recarregar da origem
            st.session_state.df_previsto_admin = pd.concat([df_previsto, df_nova], ignore_index=True)

            # 5) Bump do token para que outras páginas recarreguem quando precisarem
            bump_version_token()

            st.success(
                f"Semana '{nome_nova_semana}' criada e ativada.\n"
                f"- Duplicação: {tempo_dup:.2f}s | "
                f"Persistência (append): {tempo_salvar_base:.2f}s | "
                f"Controle: {tempo_controle:.2f}s | "
                f"Total: {time.time() - t_total:.2f}s"
            )
        except Exception as e:
            st.error("Erro ao criar a nova semana.")
            st.exception(e)

# =====================================================
# ALTERAR SEMANA ATIVA MANUALMENTE
# =====================================================
st.subheader("Alterar semana ativa manualmente")

# Em vez de depender de histórico na aba Controle, usamos as Revisões existentes
semanas_disponiveis = sorted(df_previsto["Revisão"].dropna().unique().tolist())

col1, col2 = st.columns([2, 3])
with col1:
    idx_default = semanas_disponiveis.index(semana_ativa_atual) if semana_ativa_atual in semanas_disponiveis else 0
    semana_escolhida = st.selectbox("Semana para ativar", semanas_disponiveis, index=idx_default)

with col2:
    meses_para_ativar = st.multiselect(
        "Meses liberados ao ativar",
        options=colunas_meses,
        default=meses_permitidos_atuais if meses_permitidos_atuais else (colunas_meses[-6:] if colunas_meses else []),
        format_func=formatar_mes,
        key="meses_para_ativar"
    )

if st.button("Ativar semana selecionada"):
    try:
        df_controle_ativo = pd.DataFrame({
            "Semana Ativa": [semana_escolhida],
            "Meses Permitidos": [";".join(meses_para_ativar)],
        })
        salvar_apenas_aba("Controle", df_controle_ativo)

        # Atualiza token para forçar recarga apenas quando necessário
        bump_version_token()

        st.success(f"Semana '{semana_escolhida}' definida como ativa.")
    except Exception as e:
        st.error("Erro ao ativar semana selecionada.")
        st.exception(e)

# =====================================================
# VISUALIZAÇÃO (rápida) DA BASE ATUAL
# =====================================================
st.subheader("Base de Dados atual (visualização)")

t_render = time.time()
st.dataframe(
    df_previsto.sort_values("Revisão"),
    use_container_width=True,
    height=420
)
st.markdown(
    f'<div class="timer">Tempo de renderização: {time.time() - t_render:.2f} s</div>',
    unsafe_allow_html=True
)

# =====================================================
# BOTÃO DE RECARREGAR (soft reload via token)
# =====================================================
if st.sidebar.button("Recarregar dados da origem"):
    t_reload = time.time()
    bump_version_token()
    st.sidebar.markdown(
        f'<div class="sidebar-timer">Agendada nova leitura (token). {time.time() - t_reload:.2f} s</div>',
        unsafe_allow_html=True
    )
    # Limpa apenas caches locais deste módulo
    for k in ["df_previsto_admin", "admin_colunas_meses"]:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

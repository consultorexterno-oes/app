import streamlit as st
import pandas as pd
import sys
import os
import time
from datetime import datetime

# Ajuste de path para localizar módulos internos
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from configuracoes.config import COLUNAS_ID
from entrada_saida.funcoes_io import (
    carregar_previsto,
    salvar_base_dados,
    bump_version_token,
    get_version_token,
)
from api.graph_api import carregar_semana_ativa, salvar_apenas_aba

st.set_page_config(page_title="Admin - Rota 27", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
    :root { color-scheme: light !important; }
    .stButton>button { background-color: #033347 !important; color: white !important; border-radius: 6px; font-weight: bold; }
    .status-card { background-color: #fcfcfc; border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
    .card-label { font-size: 0.85em; color: #666; font-weight: bold; text-transform: uppercase; }
    .card-value { font-size: 1.3em; color: #033347; font-weight: bold; display: block; }
    /* Estilo especial para o botão de limpar cache */
    .cache-button>button { background-color: #E2725B !important; }
    </style>
""", unsafe_allow_html=True)

# 1. Botão de Limpar Cache na Sidebar (Prominente)
with st.sidebar:
    st.markdown("### 🛠️ Ferramentas")
    if st.button("🧹 Limpar Cache do Sistema", key="btn_clear_cache"):
        st.cache_data.clear()
        bump_version_token()
        st.success("Cache limpo com sucesso!")
        time.sleep(1)
        st.rerun()
    st.markdown("---")

# 2. Autenticação
if not st.session_state.get("autenticado_admin", False):
    st.subheader("Página do Administrador - Acesso restrito 💻🔐")
    pw = st.text_input("Senha Master:", type="password")
    if st.button("Entrar"):
        if pw == "adm_oes":
            st.session_state.autenticado_admin = True
            st.rerun()
        else: st.error("Senha incorreta.")
    st.stop()

# 3. Carregamento de Dados
@st.cache_data(ttl=600)
def fetch_data(token):
    return carregar_previsto(token)

df_previsto = fetch_data(get_version_token())
controle = carregar_semana_ativa(version_token=get_version_token()) or {}

# 4. Lógica de Colunas
metadados_fixos = ["Revisão", "Cenário", "Semana", "Observações:", "ID", "DataHora"]
colunas_ignore = list(set(COLUNAS_ID + metadados_fixos))
# Identifica todas as colunas de data automaticamente
cols_m = [c for c in df_previsto.columns if c not in colunas_ignore and pd.to_datetime(c, errors='coerce', dayfirst=True) is not pd.NaT]

def safe_to_datetime(val):
    if isinstance(val, (datetime, pd.Timestamp)):
        return val
    return pd.to_datetime(val, dayfirst=True, errors='coerce')

# --- HEADER STATUS ---
st.title("⚙️ Painel de Controle Semanal")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="status-card"><span class="card-label">Semana Ativa</span><span class="card-value">{controle.get("semana", "---")}</span></div>', unsafe_allow_html=True)
with c2:
    # Como agora tudo está liberado, simplificamos o texto
    st.markdown(f'<div class="status-card"><span class="card-label">Status de Edição</span><span class="card-value">🔓 Todos os meses liberados</span></div>', unsafe_allow_html=True)

tab_create, tab_edit, tab_view = st.tabs(["🆕 Criar Nova Semana", "🔧 Ajustar Ativa", "📊 Base Completa"])

# --- ABA 1: GERAR NOVA SEMANA ---
with tab_create:
    with st.form("form_nova_semana"):
        ca, cb = st.columns(2)
        origem = ca.selectbox("Copiar dados da revisão:", sorted(df_previsto["Revisão"].unique(), reverse=True))
        novo = cb.text_input("Nome da nova semana:", placeholder="Ex: Semana 04 - v06")
        
        st.info("💡 Ao gerar a semana, todos os meses detectados na planilha serão liberados automaticamente.")
        btn_executar = st.form_submit_button("Gerar e Ativar Ciclo")

    if btn_executar:
        if not novo or novo in df_previsto["Revisão"].unique():
            st.error("Nome inválido ou semana já existente.")
        else:
            with st.status("🚀 Processando...", expanded=True) as status:
                df_nova = df_previsto[df_previsto["Revisão"] == origem].copy()
                df_nova["Revisão"] = novo
                salvar_base_dados(df_nova, append=True)
                
                # LIBERAÇÃO TOTAL: Salva todas as colunas de meses detectadas
                str_meses = ";".join([safe_to_datetime(m).strftime("%Y-%m-%d") for m in cols_m])
                df_ctrl = pd.DataFrame({"Semana Ativa": [novo], "Meses Permitidos": [str_meses]})
                
                salvar_apenas_aba("Controle", df_ctrl)
                bump_version_token()
                status.update(label="✅ Ciclo Ativado com Sucesso!", state="complete", expanded=False)
            
            st.balloons()
            time.sleep(1)
            st.rerun()

# --- ABA 2: AJUSTAR ATIVA ---
with tab_edit:
    st.subheader("Manutenção de Exibição")
    opcoes_rev = sorted(df_previsto["Revisão"].unique(), reverse=True)
    semana_atual_ctrl = controle.get("semana")
    idx_default = opcoes_rev.index(semana_atual_ctrl) if semana_atual_ctrl in opcoes_rev else 0
    
    sel_ativa = st.selectbox("Mudar semana ativa para:", opcoes_rev, index=idx_default)
    
    if st.button("Salvar Ajustes"):
        with st.spinner("Atualizando..."):
            # Garante liberação total no ajuste também
            str_meses_ajuste = ";".join([safe_to_datetime(m).strftime("%Y-%m-%d") for m in cols_m])
            df_m = pd.DataFrame({"Semana Ativa": [sel_ativa], "Meses Permitidos": [str_meses_ajuste]})
            salvar_apenas_aba("Controle", df_m)
            bump_version_token()
            st.success("Configuração atualizada!")
            time.sleep(1)
            st.rerun()

# --- ABA 3: VISUALIZAÇÃO ---
with tab_view:
    st.subheader("Base de Dados Completa")
    st.dataframe(df_previsto.sort_values("Revisão", ascending=False), use_container_width=True)

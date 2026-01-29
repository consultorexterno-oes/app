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
    </style>
""", unsafe_allow_html=True)

# 1. Autenticação
if not st.session_state.get("autenticado_admin", False):
    st.subheader("Página do Administrador - Acesso restrito 💻")
    pw = st.text_input("Senha Master:", type="password")
    if st.button("Entrar"):
        if pw == "adm_oes":
            st.session_state.autenticado_admin = True
            st.rerun()
        else: st.error("Senha incorreta.")
    st.stop()

# 2. Carregamento de Dados
@st.cache_data(ttl=600)
def fetch_data(token):
    return carregar_previsto(token)

df_previsto = fetch_data(get_version_token())
controle = carregar_semana_ativa(version_token=get_version_token()) or {}

# 3. Funções de Suporte (CORRIGIDAS)
metadados_fixos = ["Revisão", "Cenário", "Semana", "Observações:", "ID", "DataHora"]
colunas_ignore = list(set(COLUNAS_ID + metadados_fixos))
cols_m = [c for c in df_previsto.columns if c not in colunas_ignore]

def safe_to_datetime(val):
    """Converte valor para datetime garantindo o padrão brasileiro se for string."""
    if isinstance(val, (datetime, pd.Timestamp)):
        return val
    return pd.to_datetime(val, dayfirst=True, errors='coerce')

def fmt_mes(m):
    """Formata para exibição amigável Jan/26."""
    dt = safe_to_datetime(m)
    return dt.strftime("%b/%y").capitalize() if pd.notnull(dt) else str(m)

# --- HEADER STATUS ---
st.title("⚙️ Painel de Controle Semanal")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="status-card"><span class="card-label">Semana Ativa</span><span class="card-value">{controle.get("semana", "---")}</span></div>', unsafe_allow_html=True)
with c2:
    permitidos_brutos = controle.get("meses_permitidos", [])
    # DEDUPLICAÇÃO REAL NA EXIBIÇÃO: Impede Jan/26, Jan/26
    m_ativos = []
    for m in permitidos_brutos:
        label = fmt_mes(m)
        if label not in m_ativos: m_ativos.append(label)
    
    st.markdown(f'<div class="status-card"><span class="card-label">Meses Liberados</span><span class="card-value">{", ".join(m_ativos) if m_ativos else "Nenhum"}</span></div>', unsafe_allow_html=True)

tab_create, tab_edit, tab_view = st.tabs(["🆕 Criar Nova Semana", "🔧 Ajustar Ativa", "📊 Base Completa"])

# --- ABA 1: GERAR NOVA SEMANA ---
with tab_create:
    with st.form("form_nova_semana"):
        ca, cb = st.columns(2)
        origem = ca.selectbox("Copiar dados da revisão:", sorted(df_previsto["Revisão"].unique(), reverse=True))
        novo = cb.text_input("Nome da nova semana:", placeholder="Ex: Semana 04 - v05")
        
        meses_sel = st.multiselect("Liberar meses para os gerentes:", options=cols_m, 
                                    default=cols_m[-6:] if len(cols_m) >= 6 else cols_m, 
                                    format_func=fmt_mes)
        
        btn_executar = st.form_submit_button("Gerar e Ativar Ciclo")

    if btn_executar:
        if not novo or novo in df_previsto["Revisão"].unique():
            st.error("Nome inválido ou semana já existente.")
        elif not meses_sel:
            st.error("Selecione os meses que deseja liberar.")
        else:
            with st.status("🚀 Processando...", expanded=True) as status:
                df_nova = df_previsto[df_previsto["Revisão"] == origem].copy()
                df_nova["Revisão"] = novo
                salvar_base_dados(df_nova, append=True)
                
                # SALVAMENTO SEGURO: Salva em formato texto ISO para evitar confusão do Excel
                str_meses = ";".join([safe_to_datetime(m).strftime("%Y-%m-%d") for m in meses_sel])
                df_ctrl = pd.DataFrame({"Semana Ativa": [novo], "Meses Permitidos": [str_meses]})
                
                salvar_apenas_aba("Controle", df_ctrl)
                bump_version_token()
                status.update(label="✅ Ciclo Ativado!", state="complete", expanded=False)
            
            st.balloons()
            time.sleep(1)
            st.rerun()

# --- ABA 2: AJUSTAR ATIVA ---
with tab_edit:
    st.subheader("Manutenção de Exibição")
    cx, cy = st.columns(2)
    opcoes_rev = sorted(df_previsto["Revisão"].unique(), reverse=True)
    
    semana_atual_ctrl = controle.get("semana")
    idx_default = opcoes_rev.index(semana_atual_ctrl) if semana_atual_ctrl in opcoes_rev else 0
    sel_ativa = cx.selectbox("Mudar semana ativa para:", opcoes_rev, index=idx_default)
    
    # Normalização para marcar os meses corretos no multiselect
    permitidos_norm = [safe_to_datetime(m).strftime("%Y-%m-%d") for m in controle.get("meses_permitidos", [])]
    default_meses = [m for m in cols_m if safe_to_datetime(m).strftime("%Y-%m-%d") in permitidos_norm]
    
    sel_meses = cy.multiselect("Ajustar meses abertos:", options=cols_m, 
                                default=default_meses,
                                format_func=fmt_mes, key="ajuste_admin_meses")
    
    if st.button("Salvar Ajustes"):
        with st.spinner("Atualizando..."):
            str_meses_ajuste = ";".join([safe_to_datetime(m).strftime("%Y-%m-%d") for m in sel_meses])
            df_m = pd.DataFrame({"Semana Ativa": [sel_ativa], "Meses Permitidos": [str_meses_ajuste]})
            
            salvar_apenas_aba("Controle", df_m)
            bump_version_token()
            st.success("Configurações atualizadas!")
            time.sleep(1)
            st.rerun()

# --- ABA 3: VISUALIZAÇÃO ---
with tab_view:
    st.dataframe(df_previsto.sort_values("Revisão", ascending=False), use_container_width=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Forçar Recarga Global"):
    st.cache_data.clear()
    bump_version_token()
    st.rerun()

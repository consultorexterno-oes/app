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

# Estilos CSS para melhor visualização
st.markdown("""
    <style>
    :root { color-scheme: light !important; }
    .stButton>button { background-color: #033347 !important; color: white !important; border-radius: 6px; font-weight: bold; }
    .status-card { background-color: #fcfcfc; border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
    .card-label { font-size: 0.85em; color: #666; font-weight: bold; text-transform: uppercase; }
    .card-value { font-size: 1.3em; color: #033347; font-weight: bold; display: block; }
    .timer-display { background-color: #e8f5e9; color: #2e7d32; padding: 10px; border-radius: 5px; border: 1px solid #c8e6c9; font-weight: bold; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# 1. Autenticação Administrador
if not st.session_state.get("autenticado_admin", False):
    st.subheader("Página do Administrador - Acesso restrito 💻")
    pw = st.text_input("Senha Master:", type="password")
    if st.button("Entrar"):
        if pw == "adm_oes":
            st.session_state.autenticado_admin = True
            st.rerun()
        else: st.error("Senha incorreta.")
    st.stop()

# 2. Carregamento com Cache
@st.cache_data(ttl=600)
def fetch_data(token):
    return carregar_previsto(token)

df_previsto = fetch_data(get_version_token())
controle = carregar_semana_ativa(version_token=get_version_token()) or {}

# 3. Limpeza de Colunas
metadados_fixos = ["Revisão", "Cenário", "Semana", "Observações:", "ID", "DataHora"]
colunas_ignore = list(set(COLUNAS_ID + metadados_fixos))
cols_m = [c for c in df_previsto.columns if c not in colunas_ignore]

def fmt_mes(m):
    try: return pd.to_datetime(m, dayfirst=True).strftime("%b/%y").capitalize()
    except: return str(m)

# --- HEADER STATUS ---
st.title("⚙️ Painel de Controle Semanal")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f'<div class="status-card"><span class="card-label">Semana Ativa</span><span class="card-value">{controle.get("semana", "---")}</span></div>', unsafe_allow_html=True)
with c2:
    # Garantindo que meses_permitidos seja iterável para o formatador
    permitidos_brutos = controle.get("meses_permitidos", [])
    m_ativos = [fmt_mes(m) for m in permitidos_brutos]
    st.markdown(f'<div class="status-card"><span class="card-label">Meses Liberados</span><span class="card-value">{", ".join(m_ativos) if m_ativos else "Nenhum"}</span></div>', unsafe_allow_html=True)

tab_create, tab_edit, tab_view = st.tabs(["🆕 Criar Nova Semana", "🔧 Ajustar Ativa", "📊 Base Completa"])

# --- ABA 1: GERAR NOVA SEMANA ---
with tab_create:
    with st.form("form_nova_semana"):
        ca, cb = st.columns(2)
        origem = ca.selectbox("Copiar dados da revisão:", sorted(df_previsto["Revisão"].unique(), reverse=True))
        novo = cb.text_input("Nome da nova semana:", placeholder="Ex: Semana 48 - 2026")
        
        meses_sel = st.multiselect("Liberar meses para os gerentes:", options=cols_m, 
                                    default=cols_m[-6:] if len(cols_m) >= 6 else cols_m, format_func=fmt_mes)
        
        btn_executar = st.form_submit_button("Gerar e Ativar Ciclo")

    if btn_executar:
        if not novo or novo in df_previsto["Revisão"].unique():
            st.error("Nome inválido ou semana já existente.")
        else:
            t_inicio_total = time.perf_counter()
            
            with st.status("🚀 Iniciando processamento...", expanded=True) as status:
                st.write("📂 Clonando dados da revisão de origem...")
                t_step = time.perf_counter()
                df_nova = df_previsto[df_previsto["Revisão"] == origem].copy()
                df_nova["Revisão"] = novo
                st.write(f"✓ Clonagem concluída ({time.perf_counter() - t_step:.2f}s)")
                
                st.write("📡 Enviando dados para o SharePoint...")
                t_step = time.perf_counter()
                salvar_base_dados(df_nova, append=True)
                st.write(f"✓ Base de dados atualizada ({time.perf_counter() - t_step:.2f}s)")
                
                st.write("🔑 Atualizando semana ativa...")
                t_step = time.perf_counter()
                
                # AJUSTE AQUI: map(str, meses_sel) evita o TypeError com datas de 2026
                str_meses = ";".join(map(str, meses_sel))
                df_ctrl = pd.DataFrame({"Semana Ativa": [novo], "Meses Permitidos": [str_meses]})
                
                salvar_apenas_aba("Controle", df_ctrl)
                st.write(f"✓ Semana {novo} definida como ativa ({time.perf_counter() - t_step:.2f}s)")
                
                bump_version_token()
                status.update(label="✅ Tudo pronto!", state="complete", expanded=False)

            t_total = time.perf_counter() - t_inicio_total
            st.markdown(f"""
                <div class="timer-display">
                    ✅ SUCESSO! A {novo} foi gerada e ativada.<br>
                    ⏱️ Tempo total de processamento: {t_total:.2f} segundos.
                </div>
            """, unsafe_allow_html=True)
            
            st.balloons()
            time.sleep(2)
            st.rerun()

# --- ABA 2: AJUSTAR ATIVA ---
with tab_edit:
    st.subheader("Manutenção de Exibição")
    cx, cy = st.columns(2)
    opcoes_rev = sorted(df_previsto["Revisão"].unique(), reverse=True)
    
    semana_atual_ctrl = controle.get("semana")
    idx_default = opcoes_rev.index(semana_atual_ctrl) if semana_atual_ctrl in opcoes_rev else 0
    
    sel_ativa = cx.selectbox("Mudar semana ativa para:", opcoes_rev, index=idx_default)
    
    # Filtro para garantir que meses salvos existam nas colunas atuais
    default_meses = [m for m in controle.get("meses_permitidos", []) if m in cols_m]
    
    sel_meses = cy.multiselect("Ajustar meses abertos:", options=cols_m, 
                                default=default_meses,
                                format_func=fmt_mes, key="ajuste_admin")
    
    if st.button("Salvar Ajustes"):
        t_ajuste = time.perf_counter()
        with st.spinner("Salvando..."):
            # AJUSTE AQUI TAMBÉM: map(str, sel_meses)
            str_meses_ajuste = ";".join(map(str, sel_meses))
            df_m = pd.DataFrame({"Semana Ativa": [sel_ativa], "Meses Permitidos": [str_meses_ajuste]})
            
            salvar_apenas_aba("Controle", df_m)
            bump_version_token()
            st.success(f"Configurações atualizadas em {time.perf_counter() - t_ajuste:.2f}s!")
            time.sleep(1)
            st.rerun()

# --- ABA 3: VISUALIZAÇÃO ---
with tab_view:
    st.subheader("Visualização da Base Completa")
    st.dataframe(df_previsto.sort_values("Revisão", ascending=False), use_container_width=True, height=500)

# Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Forçar Recarga Global"):
    st.cache_data.clear()
    bump_version_token()
    st.rerun()
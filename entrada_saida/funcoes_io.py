import pandas as pd
import streamlit as st
import time
import requests

from configuracoes.config import COLUNAS_ID, COLUNAS_MESES
from api.graph_api import (
    baixar_aba_excel,
    baixar_arquivo_excel,
    salvar_arquivo_excel_modificado,
    salvar_aba_controle,
    salvar_apenas_aba
)

# 📥 Carrega a aba "Base de Dados"
@st.cache_data(ttl=60)
def carregar_previsto(_):
    df = baixar_aba_excel("Base de Dados")
    COLUNAS_MESES.clear()
    COLUNAS_MESES.extend([col for col in df.columns if col not in COLUNAS_ID])
    return df

# 📥 Carrega a aba "Refinado"
@st.cache_data(ttl=60)
def carregar_refinado(_, colunas_id, colunas_meses):
    try:
        return baixar_aba_excel("Refinado")
    except Exception:
        return pd.DataFrame(columns=colunas_id + ["Mes", "Valor", "Semana"])

# Função auxiliar para retry em salvamento
def _tentar_salvar(func, tentativas=5, delay_inicial=3):
    """
    Executa função de salvamento com tentativas automáticas em caso de erro 423 (Locked).
    """
    for tentativa in range(tentativas):
        try:
            return func()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 423:
                espera = delay_inicial + tentativa * 2
                st.warning(f"Arquivo bloqueado (423). Tentando novamente em {espera}s... (tentativa {tentativa+1}/{tentativas})")
                time.sleep(espera)
                continue
            raise
        except Exception as e:
            # Outros erros não relacionados a lock, parar imediatamente
            raise e
    raise Exception(f"Não foi possível salvar após {tentativas} tentativas (arquivo bloqueado).")

# 💾 Salva na aba "Base de Dados"
def salvar_base_dados(df, append=False):
    """
    Salva dados na aba 'Base de Dados'.
    - Se append=False (padrão): substitui toda a aba.
    - Se append=True: baixa a aba existente, concatena com o novo df e salva.
    """
    if not append:
        # Salva sobrescrevendo tudo (com retry)
        _tentar_salvar(lambda: salvar_apenas_aba("Base de Dados", df))
    else:
        # Salva apenas novas linhas (incremental) com retry
        def salvar_incremental():
            sheets = baixar_arquivo_excel()
            if "Base de Dados" in sheets:
                df_existente = sheets["Base de Dados"]
                df_final = pd.concat([df_existente, df], ignore_index=True)
            else:
                df_final = df
            sheets["Base de Dados"] = df_final
            salvar_arquivo_excel_modificado(sheets)

        _tentar_salvar(salvar_incremental)

# 💾 Salva na aba "Refinado"
def salvar_refinado(df, _):
    def salvar():
        sheets = baixar_arquivo_excel()
        sheets["Refinado"] = df
        salvar_arquivo_excel_modificado(sheets)

    _tentar_salvar(salvar)

# 🔄 Aplica alterações editadas pelo usuário
def aplicar_alteracoes(df_existente, df_edicoes):
    df_semana_nova = df_existente[~df_existente["Semana"].isin(df_edicoes["Semana"].unique())]
    df_final = pd.concat([df_semana_nova, df_edicoes], ignore_index=True)
    return df_final

# 📋 Duplicação baseada na coluna "Semana" da aba Refinado
def gerar_semana_duplicada(df_refinado, semana_origem, nova_semana):
    df_origem = df_refinado[df_refinado["Semana"] == semana_origem].copy()
    df_origem["Semana"] = nova_semana
    return df_origem

# 📋 Duplicação baseada na coluna "Revisão" da aba Base de Dados
def gerar_semana_a_partir_revisao(df_base, revisao_origem, nova_semana):
    df = df_base[df_base["Revisão"] == revisao_origem].copy()
    df["Revisão"] = nova_semana
    return df

# ✅ Salva aba de controle com a semana ativa
def salvar_semana_ativa(semana):
    salvar_aba_controle(semana)

# 📄 Salva o DataFrame fornecido em uma aba específica do Excel
def salvar_em_aba(df, aba="Histórico"):
    def salvar():
        sheets = baixar_arquivo_excel()
        if aba in sheets:
            sheets[aba] = pd.concat([sheets[aba], df], ignore_index=True)
        else:
            sheets[aba] = df
        salvar_arquivo_excel_modificado(sheets)

    _tentar_salvar(salvar)

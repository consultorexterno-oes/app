import time
import random
from typing import List, Set

import pandas as pd
import streamlit as st
import requests

from configuracoes.config import COLUNAS_ID, COLUNAS_MESES
from api.graph_api import (
    baixar_aba_excel,
    baixar_arquivo_excel,
    salvar_arquivo_excel_modificado,
    salvar_aba_controle,
    salvar_apenas_aba,
    carregar_semana_ativa,
)

# ============================================================
# Helpers de meses (mantém compatibilidade com o app)
# ============================================================

def _touch_meses(df: pd.DataFrame) -> None:
    """Atualiza a lista global COLUNAS_MESES com base nas colunas do DF informado."""
    COLUNAS_MESES.clear()
    COLUNAS_MESES.extend([c for c in df.columns if c not in COLUNAS_ID])

# ============================================================
# Filtragem de cenário
# ============================================================

def _filtrar_moderado(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém apenas Cenário Moderado."""
    if "Cenário" not in df.columns:
        return df
    return df[df["Cenário"].str.casefold() == "moderado"].copy()

# ============================================================
# Carregamentos (cacheados) — 1x por sessão
# ============================================================

@st.cache_data(ttl=None, show_spinner=False, max_entries=6)
def carregar_previsto(version_token: int = 0) -> pd.DataFrame:
    """Carrega a aba 'Base de Dados' (completa, somente Moderado)."""
    df = baixar_aba_excel("Base de Dados", version_token=version_token)
    df = _filtrar_moderado(df)
    _touch_meses(df)
    return df

@st.cache_data(ttl=None, show_spinner=False, max_entries=12)
def _filtrar_por_semana(df_base: pd.DataFrame, semana: str) -> pd.DataFrame:
    """Filtra uma base pela revisão (semana)."""
    if "Revisão" not in df_base.columns:
        return pd.DataFrame()
    df = df_base[df_base["Revisão"] == semana].copy()
    df = _filtrar_moderado(df)
    _touch_meses(df)
    return df

@st.cache_data(ttl=None, show_spinner=False, max_entries=1)
def carregar_previsto_semana(semana: str, version_token: int = 0) -> pd.DataFrame:
    """Carrega apenas uma semana específica (Moderado)."""
    base = carregar_previsto(version_token=version_token)
    return _filtrar_por_semana(base, semana)

@st.cache_data(ttl=None, show_spinner=False, max_entries=1)
def carregar_previsto_semana_ativa(version_token: int = 0) -> pd.DataFrame:
    """Carrega apenas a semana ativa (Controle, Moderado)."""
    info = carregar_semana_ativa(version_token=version_token)
    if not info or not info.get("semana"):
        return pd.DataFrame()
    semana = info["semana"]
    return carregar_previsto_semana(semana, version_token=version_token)

@st.cache_data(ttl=None, show_spinner=False, max_entries=2)
def carregar_refinado(version_token: int = 0,
                      colunas_id: List[str] = None,
                      colunas_meses: List[str] = None) -> pd.DataFrame:
    """Carrega aba 'Refinado' (1x por sessão, Moderado)."""
    try:
        df = baixar_aba_excel("Refinado", version_token=version_token)
        return _filtrar_moderado(df)
    except Exception:
        base_cols = (colunas_id or COLUNAS_ID) + ["Mes", "Valor", "Semana"]
        return pd.DataFrame(columns=base_cols)

# ============================================================
# Persistência com retry/backoff
# ============================================================

def _tentar_salvar(func, tentativas: int = 6, delay_inicial: float = 2.0) -> None:
    """Executa salvamento com retry/backoff (423 / timeout / conexão)."""
    for tentativa in range(1, tentativas + 1):
        try:
            return func()
        except requests.exceptions.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 423:
                espera = delay_inicial * (2 ** (tentativa - 1)) + random.uniform(0, 0.8)
                st.warning(f"Arquivo bloqueado (423). Nova tentativa em {espera:.1f}s... [{tentativa}/{tentativas}]")
                time.sleep(espera)
                continue
            raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            espera = delay_inicial * (2 ** (tentativa - 1)) + random.uniform(0, 0.8)
            st.warning(f"Instabilidade de rede. Nova tentativa em {espera:.1f}s... [{tentativa}/{tentativas}]")
            time.sleep(espera)
            continue
        except Exception:
            raise
    raise Exception("Não foi possível salvar após múltiplas tentativas.")

# ============================================================
# Utilidades de DataFrame
# ============================================================

def _safe_concat(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Concatena preservando colunas."""
    cols = list(dict.fromkeys(list(a.columns) + list(b.columns)))
    return pd.concat([a.reindex(columns=cols), b.reindex(columns=cols)], ignore_index=True)

def _substituir_por_revisao(df_existente: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    """Substitui revisões já existentes por novas linhas."""
    if "Revisão" not in df_novo.columns:
        return df_novo.copy()
    revisoes_novas: Set[str] = set(map(str, df_novo["Revisão"].dropna().unique()))
    if not revisoes_novas or "Revisão" not in df_existente.columns:
        return df_novo.copy()
    base_keep = df_existente[~df_existente["Revisão"].astype(str).isin(revisoes_novas)].copy()
    return _safe_concat(base_keep, df_novo)

# ============================================================
# Salvamentos (sempre Moderado)
# ============================================================

def salvar_base_dados(df: pd.DataFrame, append: bool = False, version_token: int = 0) -> None:
    """Salva na aba 'Base de Dados', forçando Moderado."""
    df = _filtrar_moderado(df)

    if append:
        def _append():
            try:
                df_existente = baixar_aba_excel("Base de Dados", version_token=version_token)
            except Exception:
                df_existente = pd.DataFrame(columns=df.columns)
            df_final = _safe_concat(df_existente, df)
            df_final = _filtrar_moderado(df_final)
            salvar_apenas_aba("Base de Dados", df_final, version_token=version_token or 1)
        _tentar_salvar(_append)
        return

    def _merge_and_save():
        try:
            df_existente = baixar_aba_excel("Base de Dados", version_token=version_token)
        except Exception:
            df_existente = pd.DataFrame(columns=df.columns)

        if "Revisão" in df.columns and not df.empty:
            df_final = _substituir_por_revisao(df_existente, df)
        else:
            df_final = df

        df_final = _filtrar_moderado(df_final)
        salvar_apenas_aba("Base de Dados", df_final, version_token=version_token or 1)

    _tentar_salvar(_merge_and_save)

def salvar_refinado(df: pd.DataFrame, version_token: int = 0) -> None:
    """Salva aba 'Refinado', forçando Moderado."""
    df = _filtrar_moderado(df)
    _tentar_salvar(lambda: salvar_apenas_aba("Refinado", df, version_token=version_token or 1))

def salvar_em_aba(df: pd.DataFrame, aba: str = "Histórico", version_token: int = 0) -> None:
    """Salva em aba arbitrária, mantendo Moderado."""
    df = _filtrar_moderado(df)
    def _append():
        try:
            df_existente = baixar_aba_excel(aba, version_token=version_token)
            df_final = _safe_concat(df_existente, df)
        except Exception:
            df_final = df
        df_final = _filtrar_moderado(df_final)
        salvar_apenas_aba(aba, df_final, version_token=version_token or 1)
    _tentar_salvar(_append)

# ============================================================
# Transformações de negócio
# ============================================================

def aplicar_alteracoes(df_existente: pd.DataFrame, df_edicoes: pd.DataFrame) -> pd.DataFrame:
    """Substitui linhas de semanas editadas."""
    if df_edicoes is None or df_edicoes.empty:
        return df_existente.copy()
    if "Semana" in df_edicoes.columns:
        semanas_novas = set(map(str, df_edicoes["Semana"].dropna().unique()))
    else:
        semanas_novas = set()
    if not semanas_novas or "Semana" not in df_existente.columns:
        return _safe_concat(df_existente, df_edicoes)
    base_keep = df_existente[~df_existente["Semana"].astype(str).isin(semanas_novas)].copy()
    return _safe_concat(base_keep, df_edicoes)

def gerar_semana_duplicada(df_refinado: pd.DataFrame, semana_origem: str, nova_semana: str) -> pd.DataFrame:
    """Duplica uma semana, mantendo só Moderado."""
    df_origem = df_refinado[df_refinado["Semana"] == semana_origem].copy()
    if df_origem.empty:
        return df_origem
    df_origem["Semana"] = nova_semana
    return _filtrar_moderado(df_origem)

def gerar_semana_a_partir_revisao(df_base: pd.DataFrame, revisao_origem: str, nova_semana: str) -> pd.DataFrame:
    """Gera nova semana a partir de revisão existente (apenas Moderado)."""
    df = df_base[df_base["Revisão"] == revisao_origem].copy()
    if df.empty:
        return df
    df["Revisão"] = nova_semana
    return _filtrar_moderado(df)

# ============================================================
# Controle
# ============================================================

def salvar_semana_ativa(semana: str, meses_permitidos: List[str] | None = None, version_token: int = 0) -> None:
    """Atualiza semana ativa no Controle."""
    _tentar_salvar(lambda: salvar_aba_controle(semana, meses_permitidos, version_token=version_token or 1))

# ============================================================
# Hooks de cache
# ============================================================

def bump_version_token() -> int:
    """Incrementa token de versão para forçar recarregamento cacheado."""
    if "version_token" not in st.session_state:
        st.session_state.version_token = 1
    else:
        st.session_state.version_token += 1
    return st.session_state.version_token

def get_version_token() -> int:
    """Retorna token atual de versão."""
    return st.session_state.get("version_token", 0)

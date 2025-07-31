import requests
import pandas as pd
from io import BytesIO
import streamlit as st
import urllib.parse
import time
import hashlib

# =====================================================
# CONFIGURAÇÕES DO AZURE (Secrets do Streamlit)
# =====================================================
CLIENT_ID = st.secrets["AZURE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["AZURE_CLIENT_SECRET"]
TENANT_ID = st.secrets["AZURE_TENANT_ID"]

# =====================================================
# CONFIGURAÇÕES DO SHAREPOINT
# =====================================================
DOMINIO = "osgestora.sharepoint.com"
BIBLIOTECA = "Documentos"
PASTA = "app_refinado_python"
ARQUIVO = "Teste_Refinado - Preenchimento dos gerentes.xlsx"

# =====================================================
# ENDPOINTS DO GRAPH API
# =====================================================
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
RESOURCE = "https://graph.microsoft.com/.default"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

# =====================================================
# FUNÇÕES AUXILIARES DE AUTENTICAÇÃO E BUSCA DE IDS
# =====================================================

def obter_token() -> str:
    """Obtém token de acesso para a API do Microsoft Graph com retry e timeout"""
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": RESOURCE
    }

    for tentativa in range(3):
        try:
            response = requests.post(AUTHORITY, data=payload, timeout=10)
            response.raise_for_status()
            return response.json()["access_token"]
        except requests.exceptions.RequestException as e:
            if tentativa == 2:
                raise
            time.sleep(1)  # aguarda 1s antes de nova tentativa


def buscar_site_id(token: str) -> str:
    """Obtém o ID do site principal no SharePoint"""
    url = f"{GRAPH_ROOT}/sites/{DOMINIO}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json().get("id")


def buscar_drive_id(site_id: str, token: str) -> str:
    """Obtém o ID da biblioteca de documentos (drive)"""
    url = f"{GRAPH_ROOT}/sites/{site_id}/drives"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    for drive in response.json().get("value", []):
        if drive.get("name") == BIBLIOTECA:
            return drive.get("id")

    raise FileNotFoundError(f"Biblioteca '{BIBLIOTECA}' não encontrada.")


def buscar_item_id(site_id: str, drive_id: str, token: str) -> str:
    """Obtém o ID do arquivo específico dentro do drive"""
    caminho_arquivo = f"{PASTA}/{ARQUIVO}"
    caminho_arquivo_encoded = urllib.parse.quote(caminho_arquivo)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/root:/{caminho_arquivo_encoded}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    json_resp = response.json()
    if "id" not in json_resp:
        raise FileNotFoundError(f"Arquivo '{caminho_arquivo}' não encontrado no SharePoint.")
    return json_resp["id"]

# =====================================================
# FUNÇÕES PARA DOWNLOAD DO EXCEL
# =====================================================

@st.cache_data(ttl=60)
def baixar_arquivo_excel() -> dict[str, pd.DataFrame]:
    """Baixa todas as abas do arquivo Excel como dicionário {aba: DataFrame}"""
    token = obter_token()
    site_id = buscar_site_id(token)
    drive_id = buscar_drive_id(site_id, token)
    item_id = buscar_item_id(site_id, drive_id, token)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return pd.read_excel(BytesIO(response.content), sheet_name=None)


@st.cache_data(ttl=60)
def baixar_aba_excel(nome_aba: str) -> pd.DataFrame:
    """Baixa apenas uma aba específica do arquivo Excel"""
    token = obter_token()
    site_id = buscar_site_id(token)
    drive_id = buscar_drive_id(site_id, token)
    item_id = buscar_item_id(site_id, drive_id, token)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return pd.read_excel(BytesIO(response.content), sheet_name=nome_aba)


# =====================================================
# FUNÇÕES PARA UPLOAD (SALVAR) NO EXCEL
# =====================================================

def salvar_arquivo_excel_modificado(sheets_dict: dict[str, pd.DataFrame]) -> bool:
    """Sobrescreve o arquivo inteiro com todas as abas"""
    token = obter_token()
    site_id = buscar_site_id(token)
    drive_id = buscar_drive_id(site_id, token)
    item_id = buscar_item_id(site_id, drive_id, token)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
    response = requests.put(url, headers=headers, data=output.read(), timeout=30)
    response.raise_for_status()
    return True


def salvar_apenas_aba(nome_aba: str, df_novo: pd.DataFrame) -> bool:
    """Atualiza somente a aba especificada, preservando as demais"""
    try:
        sheets = baixar_arquivo_excel()
        sheets[nome_aba] = df_novo
        return salvar_arquivo_excel_modificado(sheets)
    except Exception as e:
        st.error(f"Erro ao salvar a aba '{nome_aba}'")
        st.exception(e)
        return False


# =====================================================
# FUNÇÃO PARA CARREGAR USUÁRIOS
# =====================================================
def load_users():
    """Carrega os usuários da aba 'Usuarios'"""
    try:
        df_users = baixar_aba_excel("Usuarios")
        if df_users.empty:
            return pd.DataFrame(columns=["username", "password_hash", "role", "created_at"])
        return df_users
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {str(e)}")
        return pd.DataFrame(columns=["username", "password_hash", "role", "created_at"])

# =====================================================
# CONTROLE DE SEMANA ATIVA E MESES PERMITIDOS
# =====================================================

def salvar_aba_controle(semana: str, meses_permitidos: list[str] | None = None) -> bool:
    """Atualiza aba 'Controle' com semana ativa e meses permitidos"""
    try:
        meses_str = ";".join(meses_permitidos) if meses_permitidos else ""

        controle_df = pd.DataFrame({
            "Semana Ativa": [semana],
            "Meses Permitidos": [meses_str]
        })

        sheets = baixar_arquivo_excel()
        sheets["Controle"] = controle_df
        return salvar_arquivo_excel_modificado(sheets)
    except Exception as e:
        st.error("Erro ao salvar a aba 'Controle'")
        st.exception(e)
        return False


def carregar_semana_ativa() -> dict | None:
    """
    Retorna dicionário com semana ativa e meses permitidos:
    {"semana": str, "meses_permitidos": [lista]} ou None
    """
    try:
        sheets = baixar_arquivo_excel()
        controle_df = sheets.get("Controle", pd.DataFrame())
        if not controle_df.empty and "Semana Ativa" in controle_df.columns:
            semana = controle_df["Semana Ativa"].dropna().iloc[0]

            meses_str = controle_df.get("Meses Permitidos", pd.Series(dtype=str)).dropna().iloc[0] \
                if "Meses Permitidos" in controle_df.columns else ""

            meses_permitidos = meses_str.split(";") if meses_str else []
            return {"semana": semana, "meses_permitidos": meses_permitidos}
        return None
    except Exception as e:
        st.error("Erro ao carregar a aba 'Controle'")
        st.exception(e)
        return None


# =====================================================
# CARREGAR MESES PERMITIDOS (nova função)
# =====================================================

def carregar_meses_permitidos() -> list[str]:
    """Carrega a lista de meses permitidos da aba Controle"""
    try:
        dados_controle = carregar_semana_ativa()
        if dados_controle:
            return dados_controle.get("meses_permitidos", [])
        return []
    except Exception as e:
        st.error("Erro ao carregar meses permitidos")
        st.exception(e)
        return []

import requests
import pandas as pd
from io import BytesIO
import streamlit as st
import urllib.parse

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
    """Obtém token de acesso para a API do Microsoft Graph"""
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": RESOURCE
    }
    response = requests.post(AUTHORITY, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]


def buscar_site_id(token: str) -> str:
    """Obtém o ID do site principal no SharePoint"""
    url = f"{GRAPH_ROOT}/sites/{DOMINIO}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("id")


def buscar_drive_id(site_id: str, token: str) -> str:
    """Obtém o ID da biblioteca de documentos (drive)"""
    url = f"{GRAPH_ROOT}/sites/{site_id}/drives"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
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
    response = requests.get(url, headers=headers)
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
    response = requests.get(url, headers=headers)
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
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return pd.read_excel(BytesIO(response.content), sheet_name=nome_aba)


# =====================================================
# FUNÇÕES PARA UPLOAD (SALVAR) NO EXCEL
# =====================================================

def salvar_arquivo_excel_modificado(sheets_dict: dict[str, pd.DataFrame]) -

import requests
import pandas as pd
from io import BytesIO
import streamlit as st
import urllib.parse

# 🔐 Configurações obtidas do secrets.toml
CLIENT_ID = st.secrets["AZURE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["AZURE_CLIENT_SECRET"]
TENANT_ID = st.secrets["AZURE_TENANT_ID"]

# 📁 Caminho do arquivo no SharePoint
DOMINIO = "osgestora.sharepoint.com"
BIBLIOTECA = "Documentos"
PASTA = "app_refinado_python"
ARQUIVO = "Teste_Refinado - Preenchimento dos gerentes.xlsx"

# 🔗 URLs da Microsoft Graph
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
RESOURCE = "https://graph.microsoft.com/.default"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def obter_token():
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': RESOURCE
    }
    response = requests.post(AUTHORITY, data=payload)
    response.raise_for_status()
    return response.json()['access_token']


def buscar_site_id(token):
    url = f"{GRAPH_ROOT}/sites/{DOMINIO}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['id']


def buscar_drive_id(site_id, token):
    url = f"{GRAPH_ROOT}/sites/{site_id}/drives"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    for drive in response.json()['value']:
        if drive['name'] == BIBLIOTECA:
            return drive['id']
    raise Exception(f"Biblioteca '{BIBLIOTECA}' não encontrada.")


def buscar_item_id(site_id, drive_id, token):
    caminho_arquivo = f"{PASTA}/{ARQUIVO}"
    caminho_arquivo_encoded = urllib.parse.quote(caminho_arquivo)
    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/root:/{caminho_arquivo_encoded}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['id']


@st.cache_data(ttl=60)
def baixar_arquivo_excel():
    token = obter_token()
    site_id = buscar_site_id(token)
    drive_id = buscar_drive_id(site_id, token)
    item_id = buscar_item_id(site_id, drive_id, token)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return pd.read_excel(BytesIO(response.content), sheet_name=None)


@st.cache_data(ttl=60)
def baixar_aba_excel(nome_aba: str):
    token = obter_token()
    site_id = buscar_site_id(token)
    drive_id = buscar_drive_id(site_id, token)
    item_id = buscar_item_id(site_id, drive_id, token)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return pd.read_excel(BytesIO(response.content), sheet_name=nome_aba)


def salvar_arquivo_excel_modificado(sheets_dict):
    """Sobrescreve o arquivo inteiro com todas as abas."""
    token = obter_token()
    site_id = buscar_site_id(token)
    drive_id = buscar_drive_id(site_id, token)
    item_id = buscar_item_id(site_id, drive_id, token)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in sheets_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)

    url = f"{GRAPH_ROOT}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    response = requests.put(url, headers=headers, data=output.read())
    response.raise_for_status()
    return True


def salvar_apenas_aba(nome_aba: str, df_novo: pd.DataFrame):
    """Sobrescreve apenas a aba especificada, mantendo as outras."""
    try:
        sheets = baixar_arquivo_excel()
        sheets[nome_aba] = df_novo
        return salvar_arquivo_excel_modificado(sheets)
    except Exception as e:
        st.error(f"Erro ao salvar a aba '{nome_aba}'")
        st.exception(e)
        return False


def salvar_aba_controle(semana: str):
    """Atualiza aba de controle com a semana ativa."""
    try:
        controle_df = pd.DataFrame({"Semana Ativa": [semana]})
        sheets = baixar_arquivo_excel()
        sheets["Controle"] = controle_df
        salvar_arquivo_excel_modificado(sheets)
        return True
    except Exception as e:
        st.error("Erro ao salvar a aba 'Controle'")
        st.exception(e)
        return False


def carregar_semana_ativa():
    """Lê qual é a semana ativa a partir da aba Controle."""
    try:
        sheets = baixar_arquivo_excel()
        controle_df = sheets.get("Controle", pd.DataFrame())
        if not controle_df.empty and "Semana Ativa" in controle_df.columns:
            return controle_df["Semana Ativa"].dropna().iloc[0]
        return None
    except Exception as e:
        st.error("Erro ao carregar a aba 'Controle'")
        st.exception(e)
        return None

# acesso.py
import requests
from msal import ConfidentialClientApplication
import streamlit as st


def obter_token():
    client_id = st.secrets["AZURE_CLIENT_ID"]
    client_secret = st.secrets["AZURE_CLIENT_SECRET"]
    tenant_id = st.secrets["AZURE_TENANT_ID"]

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]

    app_msal = ConfidentialClientApplication(
        client_id, authority=authority, client_credential=client_secret
    )

    token_response = app_msal.acquire_token_for_client(scopes=scope)
    if "access_token" not in token_response:
        st.error("\u274c Erro ao gerar token de acesso.")
        st.json(token_response)
        st.stop()

    return token_response["access_token"]


def obter_site_drive_ids(headers, dominio, biblioteca):
    site_url = f"https://graph.microsoft.com/v1.0/sites/{dominio}:/"
    res_site = requests.get(site_url, headers=headers)
    if res_site.status_code != 200:
        st.error("Erro ao obter site_id do SharePoint.")
        st.json(res_site.json())
        st.stop()
    site_id = res_site.json()["id"]

    res_drive = requests.get(f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives", headers=headers)
    if res_drive.status_code != 200:
        st.error("Erro ao obter drives do SharePoint.")
        st.json(res_drive.json())
        st.stop()

    drive_id = None
    for drive in res_drive.json()["value"]:
        if drive["name"] == biblioteca:
            drive_id = drive["id"]
            break

    if not drive_id:
        st.error(f"\u274c Drive '{biblioteca}' n\u00e3o encontrado no site.")
        st.markdown("### Drives dispon\u00edveis neste site:")
        for drive in res_drive.json()["value"]:
            st.write(f"- {drive['name']}")
        st.stop()

    return site_id, drive_id


def buscar_download_url(site_id, drive_id, pasta, nome_arquivo, headers):
    url_listar = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{pasta}:/children"
    res_listar = requests.get(url_listar, headers=headers)
    if res_listar.status_code != 200:
        st.error("Erro ao listar arquivos da pasta no SharePoint.")
        st.json(res_listar.json())
        st.stop()

    for item in res_listar.json()["value"]:
        if item["name"] == nome_arquivo:
            return item["@microsoft.graph.downloadUrl"]

    st.error(f"Arquivo '{nome_arquivo}' n\u00e3o encontrado na pasta '{pasta}'.")
    st.stop()
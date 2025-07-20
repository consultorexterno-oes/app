import os
import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

client_id = os.getenv("AZURE_CLIENT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
tenant_id = os.getenv("AZURE_TENANT_ID")

authority = f"https://login.microsoftonline.com/{tenant_id}"
scopes = ["https://graph.microsoft.com/.default"]

# Inicializa MSAL app
app = ConfidentialClientApplication(
    client_id=client_id,
    client_credential=client_secret,
    authority=authority
)

# Solicita token
token_response = app.acquire_token_for_client(scopes=scopes)

if "access_token" in token_response:
    print("✅ Token gerado com sucesso!")
    access_token = token_response["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    pasta = "PlanilhasREV"
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{pasta}:/children"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        arquivos = response.json().get("value", [])
        print(f"📁 Arquivos encontrados na pasta '{pasta}':")
        for arq in arquivos:
            print(f"- {arq['name']}")
    else:
        print("❌ Erro ao acessar a pasta.")
        print(f"Código: {response.status_code}")
        print(response.text)
else:
    print("❌ Erro ao gerar token:")
    print(token_response.get("error_description"))

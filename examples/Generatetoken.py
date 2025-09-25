import os
import msal
from dotenv import load_dotenv

load_dotenv("../.env")  # adjust path to your .env

tenant = os.getenv("ENTRA_TENANT_ID")
client = os.getenv("ENTRA_CLIENT_ID")
secret = os.getenv("ENTRA_CLIENT_SECRET")
server_app_id_uri = os.getenv("SERVER_APP_ID_URI")

scope = [f"{server_app_id_uri}/.default"]   # must be a list

app = msal.ConfidentialClientApplication(
    client, authority=f"https://login.microsoftonline.com/{tenant}",
    client_credential=secret
)

result = app.acquire_token_for_client(scopes=scope)


import jwt

token = result["access_token"]
decoded = jwt.decode(token, options={"verify_signature": False})

print("Access Token:", token)
print("aud:", decoded.get("aud"))
print("iss:", decoded.get("iss"))
print("roles:", decoded.get("roles"))


#!/usr/bin/env python3
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/blogger"]
flow = InstalledAppFlow.from_client_secrets_file("acesso/blogger.json", SCOPES)

# Substitui run_console() por run_local_server()
creds = flow.run_local_server(port=0)

with open("blogger_token.json", "w") as f:
    f.write(creds.to_json())

print("✅ Token salvo em token.json")

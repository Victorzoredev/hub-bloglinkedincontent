#!/usr/bin/env python3
"""
publish_blog_to_linkedin.py
1) Busca último HTML e capa no GCS;
2) Recupera URL do último post no Blogger;
3) Gera texto do LinkedIn via OpenAI;
4) Faz upload da imagem à LinkedIn Assets API;
5) Publica no LinkedIn com a imagem via UGC API.
"""

import os
import sys
import re
import requests
from utils import load_env, get_env, init_openai_client, print_log
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import storage

# Escopo completo do Blogger API
BLOGGER_SCOPES = ["https://www.googleapis.com/auth/blogger"]


def get_blogger_service(token_file: str):
    if not os.path.exists(token_file):
        print_log(f"❌ Token file '{token_file}' não encontrado; abortando.")
        sys.exit(1)
    creds = Credentials.from_authorized_user_file(token_file, BLOGGER_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        print_log("🔄 Token de acesso Blogger atualizado.")
    return build("blogger", "v3", credentials=creds)


def main():
    print_log("=== Iniciando publish_blog_to_linkedin ===")
    load_env()
    print_log("Ambiente carregado.")

    # Env vars
    bucket_name        = get_env("BUCKET_NAME", required=True)
    html_folder        = get_env("HTML_FOLDER", "htmlblog")
    blogger_token_file = get_env("BLOGGER_TOKEN_FILE", required=True)
    blog_id            = get_env("BLOG_ID", required=True)
    chat_model         = get_env("OPENAI_CHAT_MODEL", "gpt-4o")
    linkedin_token     = get_env("LINKEDIN_ACCESS_TOKEN", required=True)
    org_urn            = os.getenv("LINKEDIN_ORGANIZATION_URN")
    person_urn         = os.getenv("LINKEDIN_PERSON_URN")

    if not (org_urn or person_urn):
        print_log("⚠️ Defina LINKEDIN_ORGANIZATION_URN ou LINKEDIN_PERSON_URN.")
        sys.exit(1)
    author = org_urn

    # 1) Buscar último HTML e capa
    print_log("Conectando ao GCS...")
    client_storage = storage.Client()
    try:
        bucket = client_storage.get_bucket(bucket_name)
    except Exception as e:
        print_log(f"❌ Erro ao acessar bucket: {e}")
        sys.exit(1)
    blobs = list(client_storage.list_blobs(bucket_name, prefix=f"{html_folder}/"))
    htmls = sorted([b.name for b in blobs if b.name.endswith('.html')])
    if not htmls:
        print_log("🔍 Nenhum HTML encontrado; abortando.")
        sys.exit(1)
    latest_html = htmls[-1]
    base = os.path.splitext(os.path.basename(latest_html))[0]
    # download HTML título
    raw_html = bucket.blob(latest_html).download_as_text()
    m = re.search(r"<title>(.*?)</title>", raw_html, re.IGNORECASE|re.DOTALL)
    post_title = m.group(1).strip() if m else base
    # imagem
    img_path = f"{html_folder}/{base}.jpg"
    blob_img = bucket.blob(img_path)
    if not blob_img.exists():
        print_log(f"❌ Imagem não encontrada: {img_path}")
        sys.exit(1)
    image_bytes = blob_img.download_as_bytes()
    print_log(f"→ HTML: {latest_html}, Título: {post_title}")

    # 2) Recuperar última URL do Blogger
    print_log("Conectando ao Blogger...")
    blog_service = get_blogger_service(blogger_token_file)
    resp = blog_service.posts().list(blogId=blog_id, maxResults=1, orderBy="PUBLISHED").execute()
    items = resp.get('items', [])
    if not items:
        print_log("❌ Nenhum post no Blogger; abortando.")
        sys.exit(1)
    post_url = items[0].get('url')
    print_log(f"→ URL: {post_url}")

    # 3) Gerar texto LinkedIn
    openai_client = init_openai_client()

    prompt = f"""
    Você é Victor, coordenador de ML & GenAI na BRLink. 
    Seu estilo no LinkedIn é direto, confiante e didático: usa perguntas retóricas,
    parágrafos curtos e listas marcadas por hífens, sem emojis ou formatação especial.

    Escreva um post em português anunciando o artigo “{post_title}”.
    Siga exatamente esta estrutura:

    1. Gancho inicial (pergunta ou afirmação provocativa).
    2. Dois a três parágrafos curtos explicando por que o tema é importante.
    3. Lista de até cinco pontos-chave usando hífens (“- ”).
    4. Chamada para ler o artigo completo no link {post_url}.
    5. Bloco final com até 8 hashtags relevantes, todas em minúsculas, separadas por espaço.

    Use tom informal, técnico-acessível, voz em primeira pessoa.
    Retorne apenas o texto final do post, sem comentários extras.
    """

    chat = openai_client.chat.completions.create(
        model=chat_model,
        messages=[{"role": "system", "content": prompt}],
        temperature = 0.7          # mais criatividade sem perder coerência
    )

    post_text = chat.choices[0].message.content.strip()
    print_log("→ Texto gerado")


    # 4) Registrar upload de asset no LinkedIn
    print_log("Registrando asset para imagem...")
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    reg_headers = {"Authorization": f"Bearer {linkedin_token}", "Content-Type":"application/json"}
    reg_resp = requests.post("https://api.linkedin.com/v2/assets?action=registerUpload", json=register_payload, headers=reg_headers)
    if reg_resp.status_code != 200:
        print_log(f"❌ Erro ao registrar upload: {reg_resp.text}")
        sys.exit(1)
    upload_info = reg_resp.json()
    asset = upload_info['value']['asset']
    upload_url = upload_info['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']

    # 5) Upload da imagem
    print_log("Enviando bytes da imagem...")
    upload_headers = {"Authorization": f"Bearer {linkedin_token}", "Content-Type": "application/octet-stream"}
    up_resp = requests.put(upload_url, data=image_bytes, headers=upload_headers)
    if up_resp.status_code not in (200,201):
        print_log(f"❌ Erro no upload da imagem: {up_resp.status_code}")
        sys.exit(1)
    print_log(f"→ Imagem carregada: {asset}")

    # 6) Publicar UGC com imagem asset
    post_payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": post_text},
            "shareMediaCategory": "IMAGE",
            "media": [{
                "status": "READY",
                "description": {"text": post_title},
                "media": asset,
                "title": {"text": post_title}
            }]
        }},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    print_log("Publicando no LinkedIn...")
    post_headers = {"Authorization": f"Bearer {linkedin_token}", "X-Restli-Protocol-Version":"2.0.0","Content-Type":"application/json"}
    post_res = requests.post("https://api.linkedin.com/v2/ugcPosts", json=post_payload, headers=post_headers)
    if post_res.status_code in (200,201):
        print_log("✅ Publicado com sucesso!")
    else:
        print_log(f"❌ Erro ao publicar: {post_res.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()
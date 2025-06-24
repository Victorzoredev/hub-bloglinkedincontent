#!/usr/bin/env python3
"""
publish_from_htmlblog_blogger.py
Lê o último HTML em 'htmlblog/' do bucket GCS, extrai o <title> para o título do post,
remove tags <title>, <html>, </html>, <!DOCTYPE html> e instâncias do título,
valida acesso ao bucket antes de gerar imagem, gera capa via OpenAI DALL·E 3 (1792x1024),
faz upload da imagem com mesmo nome do arquivo HTML, injeta como <img>,
e publica no Blogger via API v3 sem autenticação interativa.
"""

import os
import sys
import re
import requests
from utils import (
    load_env, get_env, set_gcp_credentials,
    sort_by_timestamp, print_log, init_openai_client
)
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import storage


def get_blogger_service(token_file: str):
    SCOPES = ["https://www.googleapis.com/auth/blogger"]
    if not os.path.exists(token_file):
        print_log(f"❌ Token file '{token_file}' não encontrado; abortando.")
        sys.exit(1)
    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as tok:
            tok.write(creds.to_json())
        print_log("🔄 Token de acesso atualizado.")
    return build("blogger", "v3", credentials=creds)


def main():
    print_log("=== Iniciando publish_from_htmlblog_blogger ===")
    load_env()
    print_log("Ambiente carregado.")

    bucket_name     = get_env("BUCKET_NAME", required=True)
    auth_json_path  = get_env("AUTH_JSON_PATH", required=True)
    html_folder     = get_env("HTML_FOLDER", "htmlblog")
    token_file      = get_env("BLOGGER_TOKEN_FILE", required=True)
    blog_id         = get_env("BLOG_ID", required=True)

    # Autenticação GCP
    print_log("Configurando credenciais GCP...")
    set_gcp_credentials(auth_json_path)
    # Inicializa Storage Client
    storage_client = storage.Client()
    # Valida bucket
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except Exception as e:
        print_log(f"❌ Não foi possível acessar o bucket '{bucket_name}': {e}")
        sys.exit(1)

    # Listar e escolher último HTML
    print_log(f"Buscando arquivos em '{html_folder}/'...")
    try:
        blobs = storage_client.list_blobs(bucket_name, prefix=f"{html_folder}/")
        html_blobs = [b.name for b in blobs if b.name.lower().endswith(".html")]
    except Exception as e:
        print_log(f"❌ Erro ao listar blobs: {e}")
        sys.exit(1)

    if not html_blobs:
        print_log(f"🔍 Nenhum HTML encontrado em '{html_folder}'.")
        sys.exit(1)

    latest = sort_by_timestamp(html_blobs)[-1]
    print_log(f"→ Encontrado: {latest}")

    # Baixar conteúdo HTML
    try:
        html_blob = bucket.blob(latest)
        raw_html = html_blob.download_as_text()
    except Exception as e:
        print_log(f"❌ Erro ao baixar '{latest}': {e}")
        sys.exit(1)

    # Limpeza e extração do título
    html_no_doctype = re.sub(r"<!DOCTYPE[^>]*>\s*", "", raw_html, flags=re.IGNORECASE)
    match = re.search(r"<title>(.*?)</title>", html_no_doctype, re.IGNORECASE | re.DOTALL)
    if not match:
        print_log("❌ Tag <title> não encontrada; abortando.")
        sys.exit(1)
    post_title = match.group(1).strip()
    print_log(f"→ Título extraído: '{post_title}'")

    cleaned = re.sub(r"<title>.*?</title>", "", html_no_doctype, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<html[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</html>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        rf"<h1[^>]*>\s*{re.escape(post_title)}\s*</h1>",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = cleaned.replace(post_title, "").strip()

    # Neste ponto, bucket e HTML OK — só gerar imagem
    openai_client = init_openai_client()
    print_log("Gerando capa via OpenAI")
    img_resp = openai_client.images.generate(
        model="dall-e-3",
        prompt=(
            f"Capa com estilo realista para artigo de blog intitulado '{post_title}', estilo moderno e minimalista com tamanho 1024x1792"
        ),
        size="1792x1024",
        n=1
    )
    img_url = img_resp.data[0].url

    # Upload da capa no GCS
    base_name = os.path.splitext(os.path.basename(latest))[0]
    cover_path = f"{html_folder}/{base_name}.jpg"
    cover_blob = bucket.blob(cover_path)
    try:
        image_data = requests.get(img_url).content
        cover_blob.upload_from_string(image_data, content_type="image/jpeg")
        cover_blob.make_public()
        public_img_url = cover_blob.public_url
        print_log(f"→ Capa publicada em: {public_img_url}")
    except Exception as e:
        print_log(f"❌ Erro ao fazer upload da capa: {e}")
        sys.exit(1)

    # Montar conteúdo final
    final_content = (
        f'<p><img src="{public_img_url}" alt="Capa: {post_title}" '
        'style="max-width:100%;height:auto;"></p>\n'
        + cleaned
    )

    # Publicar no Blogger
    print_log("Carregando credenciais do Blogger...")
    service = get_blogger_service(token_file)
    print_log("Publicando no Blogger...")
    body = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": post_title,
        "content": final_content
    }
    try:
        post = service.posts().insert(blogId=blog_id, body=body, isDraft=False).execute()
        print_log(f"✅ Post publicado! URL: {post.get('url')}")
    except Exception as e:
        print_log(f"❌ Erro ao publicar no Blogger: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Draft Agent: Identifica fichaum (JSON) em 'fichaum/' sem rascunho correspondente,
seleciona a mais antiga, desenvolve o conteúdo de cada tópico usando OpenAI, salva JSON em 'rascunho/'.
"""
import json
from utils import (
    load_env, get_env, set_gcp_credentials, init_storage_client, init_openai_client,
    list_blob_names, download_blob_text, upload_blob_text, get_basename, filter_json_blobs, sort_by_timestamp, print_log
)

def find_pending_fichas(fichas, rascunhos):
    names_ficha = {get_basename(f): f for f in fichas}
    names_rasc = set(get_basename(r) for r in rascunhos)
    # pending = fichas sem rascunho correspondente, em ordem cronológica
    pending = [f for name, f in names_ficha.items() if name not in names_rasc]
    pending = sort_by_timestamp(pending)
    return pending

def generate_paragraph(openai_client, topic, outline, openai_model):
    prompt = (
        f"Write a clear, engaging, and educational paragraph about the topic '{topic}' for a blog article. "
        f"The article's theme is '{outline.get('theme','')}'. "
        "Do not repeat the topic/title in the paragraph. "
        "Keep the text approachable and focused on technology, statistics, or artificial intelligence as relevant."
    )
    response = openai_client.chat.completions.create(
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a specialist in technology, statistics, and AI. "
                    "Your writing should be informative, friendly, and suitable for a blog post. Write only the paragraph."
                )
            },
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def main():
    load_env()
    BUCKET_NAME = get_env("BUCKET_NAME", required=True)
    AUTH_JSON_PATH = get_env("AUTH_JSON_PATH")
    FICHA_FOLDER = get_env("FICHAUM_FOLDER", "fichaum")
    RASCUNHO_FOLDER = get_env("RASCUNHO_FOLDER", "rascunho")
    OPENAI_MODEL = get_env("OPENAI_MODEL", "gpt-4.1")
    set_gcp_credentials(AUTH_JSON_PATH)

    client, bucket_name = init_storage_client()
    openai_client = init_openai_client()

    fichas = filter_json_blobs(list_blob_names(client, bucket_name, FICHA_FOLDER))
    rascunhos = filter_json_blobs(list_blob_names(client, bucket_name, RASCUNHO_FOLDER))
    pending = find_pending_fichas(fichas, rascunhos)
    if not pending:
        print_log("Nenhuma ficha pendente para gerar rascunho.")
        return

    target_ficha = pending[0]
    print_log(f"Processando ficha pendente: {target_ficha}")

    ficha_data = json.loads(download_blob_text(client, bucket_name, target_ficha))
    theme = ficha_data.get('theme')
    topics = ficha_data.get('topics', [])
    timestamp = get_basename(target_ficha).replace('.json', '')

    draft_content = {}
    for t in topics:
        print_log(f"Gerando parágrafo para tópico: {t}")
        draft_content[t] = generate_paragraph(openai_client, t, ficha_data, OPENAI_MODEL)

    draft = {
        'timestamp': ficha_data.get('timestamp', timestamp),
        'theme': theme,
        'topics': topics,
        'draft': draft_content
    }
    output_name = f"{RASCUNHO_FOLDER}/{timestamp}.json"
    upload_blob_text(client, bucket_name, output_name, json.dumps(draft, ensure_ascii=False, indent=2))
    print_log(f"Rascunho salvo em gs://{bucket_name}/{output_name}")

if __name__ == "__main__":
    main()
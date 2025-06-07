#!/usr/bin/env python3
"""
Head Agent: Busca as últimas 5 fichas em 'fichaum/' do bucket GCS em ordem cronológica,
chama o OpenAI SDK (modelo gpt-4o) para extrair tema e tópicos (JSON puro),
e salva a nova ficha em um novo arquivo JSON na pasta configurada.
"""

import json
import re
from datetime import datetime
from utils import (
    load_env, get_env, set_gcp_credentials, init_storage_client, init_openai_client,
    list_blob_names, download_blob_text, upload_blob_text, filter_json_blobs, sort_by_timestamp, print_log
)

def fetch_last_jsons(client, bucket_name, prefix, n=5):
    blob_names = list_blob_names(client, bucket_name, prefix)
    json_blobs = filter_json_blobs(blob_names)
    json_blobs = sort_by_timestamp(json_blobs)
    # oldest to newest
    recent = json_blobs[-n:] if len(json_blobs) >= n else json_blobs
    # Pad with "vazio" if not enough articles
    texts = []
    for i in range(n):
        if i < len(recent):
            texts.append(download_blob_text(client, bucket_name, recent[i]))
        else:
            texts.append("vazio")
    return texts

def build_prompt(json_texts):
    # Caso seja o primeiro post do blog
    if all(x == "vazio" for x in json_texts):
        return (
            "You are creating the very first post of an educational blog focused on technology, statistics, and artificial intelligence. "
            "Generate a main theme for the first article and suggest five topics that should be addressed in this opening post—"
            "making sure the fifth topic is a clear conclusion summarizing the article. "
            "Return ONLY a JSON object with keys 'theme' and 'topics' (a list of 5 items, where the last item is the conclusion). "
            "No explanations or markdown, just valid JSON."
        )

    # Caso já existam artigos anteriores
    articles = [
        f"Article {i+1}: {json_texts[i]}"
        for i in range(len(json_texts))
        if json_texts[i] != "vazio"
    ]
    articles_block = "\n\n".join(articles)

    return (
        "You are the editor of a technology, statistics, and AI blog. "
        "Analyze the chronological order of the last articles (oldest to newest) below:\n\n"
        f"{articles_block}\n\n"
        "Based on these, suggest a relevant new theme for the next article and propose five fresh and engaging topics—"
        "ensuring the fifth topic serves as a conclusion summarizing the key points. "
        "Respond ONLY with a JSON object containing 'theme' (string) and 'topics' (list of 5 strings, "
        "with the last string being the conclusion). No markdown, just plain JSON."
    )

def strip_md_fence(text):
    """
    Remove markdown fences ```json ... ``` e espaços extras.
    """
    text = text.strip()
    # Remove fence no início e fim (suporta tanto ```json quanto ```)
    text = re.sub(r"^```[a-z]*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
    return text.strip()

def main():
    load_env()
    BUCKET_NAME = get_env("BUCKET_NAME", "linkedin-article")
    AUTH_JSON_PATH = get_env("AUTH_JSON_PATH", None)
    FICHAUM_FOLDER = get_env("FICHAUM_FOLDER", "fichaum")
    OPENAI_MODEL = get_env("OPENAI_MODEL", "o3-2025-04-16")
    set_gcp_credentials(AUTH_JSON_PATH)

    client, bucket_name = init_storage_client()
    openai_client = init_openai_client()

    last_jsons = fetch_last_jsons(client, bucket_name, FICHAUM_FOLDER, n=5)
    prompt = build_prompt(last_jsons)
    print_log("Prompt for OpenAI built.")

    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an assistant that identifies the theme and topics of articles for a tech/statistics/AI blog."},
            {"role": "user", "content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    content = strip_md_fence(content)  # <-- Aqui garante que não tem fences
    try:
        data = json.loads(content)
    except Exception:
        print_log("ERRO: JSON inválido. Resposta crua abaixo e não será salva:")
        print(content)
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{FICHAUM_FOLDER}/{timestamp}.json"
    upload_blob_text(client, bucket_name, filename, json.dumps(data, ensure_ascii=False, indent=2))
    print_log(f"Nova ficha salva em gs://{bucket_name}/{filename}")

if __name__ == "__main__":
    main()
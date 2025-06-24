#!/usr/bin/env python3
"""
head_agent.py
Head Agent: busca as últimas 5 fichas em 'fichaum/' do bucket GCS em ordem cronológica,
chama o OpenAI SDK (modelo gpt-4o) para extrair tema e tópicos (JSON puro),
e salva a nova ficha em um novo arquivo JSON na pasta configurada.
"""

import json
import re
from datetime import datetime
from utils import (
    load_env, get_env, set_gcp_credentials, init_storage_client, init_openai_client,
    list_blob_names, download_blob_text, upload_blob_text,
    filter_json_blobs, sort_by_timestamp, print_log
)

def fetch_last_jsons(client, bucket, prefix, n=5):
    names = list_blob_names(client, bucket, prefix)
    json_blobs = filter_json_blobs(names)
    json_blobs = sort_by_timestamp(json_blobs)
    recent = json_blobs[-n:] if len(json_blobs) >= n else json_blobs
    texts = []
    for i in range(n):
        texts.append(download_blob_text(client, bucket, recent[i]) if i < len(recent) else "vazio")
    return texts

def build_prompt(json_texts):
    # se for o primeiro post
    if all(x == "vazio" for x in json_texts):
        return (
            "Você está criando o primeiro post de um blog educacional focado em tecnologia, estatística e inteligência artificial. "
            "Gere um tema principal para o primeiro artigo e sugira cinco tópicos que devem ser abordados neste post de abertura — "
            "garantindo que o quinto tópico seja uma conclusão clara que resuma o artigo. "
            "Retorne SOMENTE um objeto JSON com as chaves 'theme' e 'topics' (uma lista de 5 itens, onde o último item é a conclusão). "
            "Sem explicações ou markdown, apenas JSON válido."
        )

    artigos = [
        f"Artigo {i+1}: {json_texts[i]}"
        for i in range(len(json_texts))
        if json_texts[i] != "vazio"
    ]
    bloco = "\n\n".join(artigos)

    return (
        "Você é um especialista em machine learning e inteligência artificial, coordenador de um time que desenvolve projetos de IA utilizando AWS e editor de um blog de tecnologia, estatística e inteligência artificial."
        "Analise a ordem cronológica dos últimos artigos do seu blog (do mais antigo ao mais recente) abaixo:\n\n"
        f"{bloco}\n\n"
        "Com base nisso, sugira um novo tema relevante para o próximo artigo e proponha cinco tópicos novos e envolventes — Seu publico alvo são profissionais de tecnologia, estatística e IA. Porem o conteúdo deve ser acessível a iniciantes e empreendedores."
        "Os artigos devem ter caracter educativo, com foco na parte matemática e estatística, mas também com aplicações práticas em IA e machine learning."
        "O artigo deve ter uma apresentação clara e objetiva, falar sobre as vantegens e desvantagens de cada abordagem, e incluir exemplos práticos."
        "O quinto tópico deve ser uma conclusão que resuma o artigo e ofereça uma visão geral do tema."
        "Responda SOMENTE com um objeto JSON contendo 'theme' (string) e 'topics' (lista de 5 strings, "
        "com a última string sendo a conclusão). Sem markdown, apenas JSON."
    )

def strip_md_fence(text):
    text = text.strip()
    text = re.sub(r"^```[a-z]*\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
    return text.strip()

def main():
    print_log("=== Iniciando head_agent ===")
    load_env()
    print_log("Ambiente carregado.")

    BUCKET       = get_env("BUCKET_NAME", required=True)
    AUTH_JSON    = get_env("AUTH_JSON_PATH")
    FICHA_FOLDER = get_env("FICHAUM_FOLDER", "fichaum")
    OPENAI_MODEL = get_env("OPENAI_MODEL", "gpt-4o")

    print_log("Configurando credenciais GCP e clientes...")
    set_gcp_credentials(AUTH_JSON)
    client, bucket = init_storage_client()
    openai_client = init_openai_client()

    print_log(f"Buscando últimas fichas em '{FICHA_FOLDER}'...")
    last_jsons = fetch_last_jsons(client, bucket, FICHA_FOLDER, n=5)
    existentes = len([x for x in last_jsons if x != "vazio"])
    print_log(f"{existentes} fichas encontradas; criando prompt...")

    prompt = build_prompt(last_jsons)
    print_log("Prompt construído. Chamando OpenAI...")
    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Você é um assistente que identifica o tema e tópicos de artigos para um blog de tecnologia, estatística e IA."},
            {"role": "user",   "content": prompt}
        ]
    )

    conteudo = resp.choices[0].message.content.strip()
    conteudo = strip_md_fence(conteudo)
    print_log("Resposta recebida. Processando JSON...")

    try:
        data = json.loads(conteudo)
    except Exception:
        print_log("ERRO: JSON inválido. Resposta crua abaixo e não será salva:")
        print_log(conteudo)
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{FICHA_FOLDER}/{timestamp}.json"
    upload_blob_text(client, bucket, filename, json.dumps(data, ensure_ascii=False, indent=2))
    print_log(f"✅ Nova ficha salva em gs://{bucket}/{filename}")

if __name__ == "__main__":
    main()
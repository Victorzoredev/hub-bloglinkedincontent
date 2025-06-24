#!/usr/bin/env python3
"""
design_agent.py
Design Agent: lê o JSON de rascunho em 'rascunho/' que ainda não possui HTML correspondente em 'htmlblog/',
seleciona o mais antigo, chama o OpenAI SDK para gerar HTML minimalista responsivo,
com código sempre em <pre><code>, salva no bucket GCS em 'htmlblog/'.
"""

import json
import os
from utils import (
    load_env, get_env, set_gcp_credentials, init_storage_client, init_openai_client,
    list_blob_names, download_blob_text, upload_blob_text, get_basename, filter_json_blobs, print_log
)

CSS_CONTENT = (
    ":root {"
    "  --max-width: 800px;"
    "  --padding: 16px;"
    "  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;"
    "  --line-height: 1.6;"
    "  --heading-color: #232323;"
    "  --text-color: #222;"
    "  --background-color: #f9f9f9;"
    "  --gap: 1em;"
    "}"
    "body {"
    "  margin: 0;"
    "  padding: 0;"
    "  font-family: var(--font-family);"
    "  line-height: var(--line-height);"
    "  color: var(--text-color);"
    "  background: var(--background-color);"
    "  padding: var(--padding);"
    "}"
    ".container {"
    "  max-width: var(--max-width);"
    "  margin: 0 auto;"
    "}"
    "h1, h2 {"
    "  color: var(--heading-color);"
    "  margin-bottom: calc(var(--gap) / 2);"
    "  text-align: left;"
    "}"
    "h1 { font-size: 1.75em; margin-top: var(--gap); }"
    "h2 { font-size: 1.25em; margin-top: var(--gap); }"
    "p { margin-bottom: var(--gap); text-align: left; }"
    "pre, code { background: #ededed; color: #333; border-radius: 8px; padding: 4px 8px; }"
    "@media (max-width: 600px) {"
    "  body { padding: 8px; }"
    "  h1 { font-size: 1.35em; }"
    "  h2 { font-size: 1.1em; }"
    "}"
)

def build_prompt(theme, topics, draft):
    # instruções originais, sem alterações
    header = (
        """CONTEXT:
You are a content formatter for educational blogs in Statistics, Machine Learning, and AI. Your task is to generate a complete, responsive HTML5 document with a minimalist, readable design on any device.

RULES:
1. Begin output with <!DOCTYPE html>.
2. Include <html>, <head>, and <body> tags.
3. In <head>, include:
   - <meta charset="UTF-8">
   - <meta name="viewport" content="width=device-width, initial-scale=1.0">
   - <title> based on the theme
   - A <style> block with the provided CSS.
4. In <body>, wrap content in <div class="container">.
5. Use <h1> for the main theme.
6. For each topic:
   - <h2> for the topic title.
   - <p> for the paragraph content.
7. Format any code or command examples with <pre><code>…</code></pre>, make sure the code stays inside the code "box"
8. Use <strong>, <em>, and lists (<ul><li>) to highlight key concepts.
9. Do not use code fences (```).

OUTPUT:
Only the complete HTML as specified above, with no extra text.  
Write all content in Portuguese-BR."""
    )

    lista_topicos = "\n".join(f"- {t}" for t in topics)
    paragrafos = "\n".join(
        f"<h2>{t}</h2>\n<p>{draft['draft'].get(t, '')}</p>"
        for t in topics
    )

    prompt = "\n".join([
        header,
        f"Tema: {theme}",
        "Tópicos a cobrir:",
        lista_topicos,
        "Inclua este CSS exatamente na tag <style>:",
        CSS_CONTENT,
        "Parágrafos já gerados (não reescrever):",
        paragrafos
    ])

    return prompt

def find_pending_rascunhos(rascunhos, htmls):
    rasc_map = {os.path.splitext(get_basename(r))[0]: r for r in rascunhos}
    html_keys = {
        os.path.splitext(get_basename(h))[0]
        for h in htmls if h.endswith('.html')
    }
    pending = sorted(k for k in rasc_map if k not in html_keys)
    return [rasc_map[k] for k in pending]

def main():
    print_log("=== Iniciando design_agent ===")

    load_env()
    print_log("Ambiente carregado.")

    BUCKET_NAME     = get_env("BUCKET_NAME", required=True)
    AUTH_JSON_PATH  = get_env("AUTH_JSON_PATH")
    RASCUNHO_FOLDER = get_env("RASCUNHO_FOLDER", "rascunho")
    HTML_FOLDER     = get_env("HTML_FOLDER", "htmlblog")
    OPENAI_MODEL    = get_env("OPENAI_MODEL", "gpt-4.1")

    print_log("Configurando credenciais GCP e clientes...")
    set_gcp_credentials(AUTH_JSON_PATH)
    client, bucket = init_storage_client()
    openai_client  = init_openai_client()

    print_log(f"Listando rascunhos em '{RASCUNHO_FOLDER}' e HTMLs em '{HTML_FOLDER}'...")
    rascs = filter_json_blobs(list_blob_names(client, bucket, RASCUNHO_FOLDER))
    htmls = list_blob_names(client, bucket, HTML_FOLDER)
    print_log(f"→ {len(rascs)} rascunhos, {len(htmls)} HTMLs já existentes.")

    pendings = find_pending_rascunhos(rascs, htmls)
    if not pendings:
        print_log("🔍 Nenhum rascunho pendente para gerar HTML.")
        return

    target = pendings[0]
    print_log(f"📄 Processando rascunho: {target}")
    draft_data = json.loads(download_blob_text(client, bucket, target))

    theme  = draft_data.get('theme')
    topics = draft_data.get('topics', [])
    if not theme or not topics:
        print_log("❌ Rascunho sem 'theme' ou 'topics' – abortando.")
        return

    prompt = build_prompt(theme, topics, draft_data)
    print_log("Prompt para OpenAI construído. Chamando OpenAI...")
    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a highly precise HTML formater. Transform the content in a beautiful blog article. Only output the requested HTML."},
            {"role": "user",   "content": prompt}
        ]
    )

    html_content = resp.choices[0].message.content.strip()
    base = os.path.splitext(get_basename(target))[0]
    output_path = f"{HTML_FOLDER}/{base}.html"
    upload_blob_text(client, bucket, output_path, html_content,
                     content_type="text/html; charset=utf-8")
    print_log(f"✅ HTML gerado e salvo em gs://{bucket}/{output_path}")

if __name__ == "__main__":
    main()
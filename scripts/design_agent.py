#!/usr/bin/env python3
"""
Design Agent: lê o JSON de rascunho em 'rascunho/' que ainda não possui HTML correspondente em 'htmlblog/',
seleciona o mais antigo, chama o OpenAI SDK para gerar HTML minimalista responsivo, 
com código sempre em <pre><code>, salva no bucket GCS em 'htmlblog/'.
"""
import argparse
import json
import os
from utils import (
    load_env, get_env, set_gcp_credentials, init_storage_client, init_openai_client,
    list_blob_names, download_blob_text, upload_blob_text, get_basename, filter_json_blobs, print_log
)

CSS_CONTENT = (
    ":root {"
    "  --max-width: 600px;"
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

def build_prompt(theme, topics, draft, lang):
    topics_list_str = "\n".join([f"- {t}" for t in topics])
    paragraphs = ""
    for t in topics:
        content = draft['draft'].get(t, "")
        paragraphs += f"\n<h2>{t}</h2>\n<p>{content}</p>"
    if lang == "pt":
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
7. Format any code or command examples with <pre><code>…</code></pre>.
8. Use <strong>, <em>, and lists (<ul><li>) to highlight key concepts.
9. Do not use code fences (```).

OUTPUT:
Only the complete HTML as specified above, with no extra text.  
Write all content in Portuguese-BR."""
        )
    else:
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
   - Use short, clear paragraphs.
7. Format any code or command examples with <pre><code>…</code></pre>.
8. Use <strong>, <em>, and lists (<ul><li>) to highlight key concepts.
9. Do not use code fences (```).

OUTPUT:
Only the complete HTML as specified above, with no extra text.  
Write all content in English."""
        )
    return (
        header + "\n"
        "Theme: " + theme + "\n"
        "Topics to cover:\n" + topics_list_str + "\n"
        "Embed this CSS exactly in the <style> tag:\n" + CSS_CONTENT + "\n"
        "Paragraphs already generated (do NOT rephrase):\n" + paragraphs
    )

def find_pending_rascunhos(rascunhos, htmls, lang):
    rasc_map = {os.path.splitext(get_basename(r))[0]: r for r in rascunhos}
    html_keys = {
        os.path.splitext(get_basename(h))[0].split('-')[0]
        for h in htmls if h.endswith(f"-{lang}.html")
    }
    pending_keys = sorted(k for k in rasc_map if k not in html_keys)
    return [rasc_map[k] for k in pending_keys]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", type=str, default="en", help="Target language for HTML file (e.g., en, pt)")
    args = parser.parse_args()

    load_env()
    BUCKET_NAME = get_env("BUCKET_NAME", required=True)
    AUTH_JSON_PATH = get_env("AUTH_JSON_PATH")
    RASCUNHO_FOLDER = get_env("RASCUNHO_FOLDER", "rascunho")
    HTML_FOLDER = get_env("HTML_FOLDER", "htmlblog")
    OPENAI_MODEL = get_env("OPENAI_MODEL", "gpt-4.1")
    set_gcp_credentials(AUTH_JSON_PATH)

    client, bucket_name = init_storage_client()
    openai_client = init_openai_client()

    rascunhos = filter_json_blobs(list_blob_names(client, bucket_name, RASCUNHO_FOLDER))
    htmls = list_blob_names(client, bucket_name, HTML_FOLDER)
    pendings = find_pending_rascunhos(rascunhos, htmls, args.lang)
    if not pendings:
        print_log(f"No draft found for HTML generation in '{args.lang}'.")
        return

    target = pendings[0]
    print_log(f"Processing draft: {target}")
    draft_data = json.loads(download_blob_text(client, bucket_name, target))
    theme = draft_data.get('theme')
    topics = draft_data.get('topics', [])
    if not theme or not topics:
        print_log("Draft missing theme or topics.")
        return
    base_name = os.path.splitext(get_basename(target))[0]
    prompt = build_prompt(theme, topics, draft_data, args.lang)

    resp = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a highly precise HTML formater. Transform the content in a beaultiful blog article. Only output the requested HTML."},
            {"role": "user", "content": prompt}
        ]
    )
    html_content = resp.choices[0].message.content.strip()
    output_path = f"{HTML_FOLDER}/{base_name}-{args.lang}.html"
    upload_blob_text(client, bucket_name, output_path, html_content, content_type="text/html; charset=utf-8")
    print_log(f"✅ HTML gerado e salvo em gs://{bucket_name}/{output_path}")

if __name__ == "__main__":
    main()
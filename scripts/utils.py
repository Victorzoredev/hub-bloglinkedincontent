# utils.py
import os
import json
from typing import List, Optional
from google.cloud import storage
import openai

def load_env():
    from dotenv import load_dotenv
    load_dotenv()

def get_env(key, default=None, required=False):
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Variável de ambiente {key} não definida")
    return value

def set_gcp_credentials(auth_json_path: Optional[str]):
    AUTH_JSON_PATH = get_env("AUTH_JSON_PATH", None)
    if auth_json_path:
        os.environ['AUTH_JSON_PATH'] = auth_json_path

def init_storage_client():
    bucket_name = get_env("BUCKET_NAME", required=True)
    # storage.Client() já vai usar a conta ativa no CLI se a env GOOGLE_APPLICATION_CREDENTIALS não estiver setada!
    return storage.Client(), bucket_name

def init_openai_client():
    api_key = get_env("OPENAI_API_KEY", required=True)
    return openai.OpenAI(api_key=api_key)

def list_blob_names(client, bucket_name, prefix) -> List[str]:
    return [b.name for b in client.list_blobs(bucket_name, prefix=f"{prefix}/")]

def download_blob_text(client, bucket_name, blob_name) -> str:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_text()

def upload_blob_text(client, bucket_name, blob_name, content, content_type="application/json"):
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(content, content_type=content_type)

def filter_json_blobs(blob_names: List[str]) -> List[str]:
    return [b for b in blob_names if b.lower().endswith('.json')]

def get_basename(blob_name: str) -> str:
    import os
    return os.path.basename(blob_name)

def strip_md_fence(text: str) -> str:
    lines = text.strip().splitlines()
    cleaned = [l for l in lines if not l.strip().startswith("```")]
    return "\n".join(cleaned)

def extract_html_block(content: str) -> str:
    lines = content.splitlines()
    cleaned_lines = []
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block:
            cleaned_lines.append(line)
    full_content = "\n".join(cleaned_lines).strip()
    start_idx = full_content.find("<!DOCTYPE html>")
    if start_idx == -1:
        start_idx = full_content.find("<html>")
    end_idx = full_content.rfind("</html>")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return full_content[start_idx:end_idx+len("</html>")].strip()
    return full_content.strip()

def print_log(msg):
    from datetime import datetime
    print(f"[{datetime.utcnow().isoformat()}] {msg}")

def sort_by_timestamp(blob_names: List[str]) -> List[str]:
    return sorted(blob_names, key=lambda x: get_basename(x))
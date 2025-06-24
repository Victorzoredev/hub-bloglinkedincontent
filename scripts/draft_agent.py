#!/usr/bin/env python3
"""
draft_agent.py  (versão simplificada – rascunho em uma única chamada)

• Procura a ficha JSON mais antiga em 'fichaum/' que ainda não tenha rascunho em 'rascunho/'.
• Envia a ficha inteira para o modelo OpenAI de uma só vez.
• O modelo devolve **um único objeto JSON** contendo, para cada tópico, um parágrafo de rascunho.
• Salva o JSON resultante em 'rascunho/'.
"""

import json
import os
import sys
from utils import (
    load_env, get_env, set_gcp_credentials,
    init_storage_client, init_openai_client,
    list_blob_names, download_blob_text, upload_blob_text,
    print_log
)

# --------------------------------------------------------------------------- #
# Funções utilitárias                                                         #
# --------------------------------------------------------------------------- #

def pegar_ficha_pendente(client, bucket, pasta_ficha, pasta_rasc):
    """Retorna (caminho_blob, nome_base) da ficha sem rascunho correspondente."""
    fichas = sorted(
        f for f in list_blob_names(client, bucket, pasta_ficha) if f.endswith(".json")
    )
    existentes = {
        os.path.splitext(os.path.basename(r))[0]
        for r in list_blob_names(client, bucket, pasta_rasc) if r.endswith(".json")
    }
    for caminho in fichas:
        base = os.path.splitext(os.path.basename(caminho))[0]
        if base not in existentes:
            return caminho, base
    return None, None


def gerar_rascunho_em_uma_chamada(
    openai_client,
    model: str,
    ficha_data: dict,
) -> dict:
    """Pede ao modelo que devolva o JSON completo com todos os tópicos escritos."""

    # ----- prompt do sistema (estilo e estrutura) -------------------------- #
    system_prompt = """
Você é Victor, coordenador de ML & GenAI na BRLink e especialista em soluções AWS.

Objetivo → escrever um artigo educativo (quase científico) em português do Brasil.

Diretrizes de estilo
- Tom direto, confiante e didático, porém acessível.
- Parágrafos curtos (máx. 3 linhas cada) para ritmo fluido.
- Listas marcadas por hífen (“- ”) quando necessário.
- Nenhum emoji ou formatação especial (sem **negrito**, _itálico_ ou markdown).
- Afirme apenas o que for comprovado; evite especulações.

Estrutura recomendada
1. Título instigante  
2. Resumo de 1 frase  
3. Contexto e motivação  
4. Pergunta central ou hipótese  
5. Abordagem / método (passo a passo)  
6. Principais achados (lista)  
7. Implicações práticas  
8. Limitações ou contrapartidas  
9. Próximos passos / chamada à ação  
10. Referências leves  

Sua tarefa agora:
Receberá um objeto JSON com os campos
{
  "timestamp": "...",
  "theme": "...",
  "topics": ["tópico 1", "tópico 2", ...]
}

Crie um novo objeto JSON mantendo os campos originais **e** acrescentando
"draft": { "<tópico 1>": "<parágrafo>", "<tópico 2>": "<parágrafo>", ... }

• Escreva um único parágrafo (máx. 3 linhas) para cada tópico seguindo as diretrizes acima.  
• Retorne **apenas** o JSON válido (sem texto extra, cabeçalhos ou markdown).  
"""

    user_message = json.dumps(ficha_data, ensure_ascii=False)

    print_log("🧑‍💻 Chamando OpenAI para gerar rascunho completo...")
    resp = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.55,
    )

    raw_answer = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw_answer)
    except json.JSONDecodeError:
        print_log("⚠️ Falha ao decodificar JSON. Conteúdo bruto retornado pelo modelo:")
        print(raw_answer)
        raise


# --------------------------------------------------------------------------- #
# Pipeline principal                                                          #
# --------------------------------------------------------------------------- #

def main():
    print_log("=== Iniciando draft_agent ===")
    load_env()
    print_log("Ambiente carregado.")

    BUCKET        = get_env("BUCKET_NAME", required=True)
    AUTH_JSON     = get_env("AUTH_JSON_PATH", required=True)
    FICHA_FOLDER  = get_env("FICHAUM_FOLDER", "fichaum")
    RASC_FOLDER   = get_env("RASCUNHO_FOLDER", "rascunho")
    MODEL         = get_env("OPENAI_MODEL", "gpt-4o")

    print_log("Configurando GCP e clientes...")
    set_gcp_credentials(AUTH_JSON)
    client, bucket = init_storage_client()
    openai_client  = init_openai_client()

    print_log("Procurando ficha pendente...")
    caminho, base = pegar_ficha_pendente(client, bucket, FICHA_FOLDER, RASC_FOLDER)
    if not caminho:
        print_log("🔍 Nenhuma ficha pendente encontrada.")
        return

    print_log(f"📄 Ficha selecionada: {caminho}")
    ficha_raw   = download_blob_text(client, bucket, caminho)
    ficha_data  = json.loads(ficha_raw)

    # --- gera rascunho completo em uma única chamada ------------- #
    rascunho_completo = gerar_rascunho_em_uma_chamada(
        openai_client, MODEL, ficha_data
    )

    # --- grava rascunho ------------------------------------------ #
    destino = f"{RASC_FOLDER}/{base}.json"
    upload_blob_text(
        client,
        bucket,
        destino,
        json.dumps(rascunho_completo, ensure_ascii=False, indent=2),
    )
    print_log(f"✅ Rascunho salvo em gs://{BUCKET}/{destino}")


if __name__ == "__main__":
    main()
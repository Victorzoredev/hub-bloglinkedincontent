#!/usr/bin/env bash
set -euo pipefail

# --- Parâmetros de Entrada ---
# Use $1 para o nome do bucket e $2 para o nome do arquivo/pasta
# Defina valores padrão se não forem fornecidos

BUCKET=${1:-article_linkedin} # $1 é o primeiro argumento. ':-' define um valor padrão
FOLDER=${2:-data}           # $2 é o segundo argumento
REGION=${3:-US}            # $3 é o terceiro argumento, se quiser flexibilizar a região
PROJECT=$(gcloud config get-value project)

# --- Verificação de Argumentos (Opcional, mas recomendado) ---
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Uso: $0 <nome_do_bucket> <nome_da_pasta>"
  echo "Exemplo: $0 meu-bucket-teste minha-pasta-de-dados"
  exit 1
fi

# 1) Cria o bucket (se ainda não existir)
if gcloud storage buckets describe gs://${BUCKET} &>/dev/null; then
  echo "ℹ️ Bucket ${BUCKET} já existe (project=${PROJECT})."
else
  gcloud storage buckets create gs://${BUCKET} \
    --location=${REGION} \
    --project=${PROJECT}
  echo "✅ Bucket ${BUCKET} criado em ${REGION}."
fi

# 2) Cria um marcador de “pasta” usando um objeto .keep
if gsutil ls gs://${BUCKET}/${FOLDER}/.keep &>/dev/null; then
  echo "ℹ️ Marker .keep já existe em gs://${BUCKET}/${FOLDER}/"
else
  echo -n "" | gsutil cp - gs://${BUCKET}/${FOLDER}/.keep
  echo "📂 Pasta '${FOLDER}/' criada (marker .keep) em gs://${BUCKET}/"
fi
````markdown
# LinkedIn Content-Hub 🛰️  
*Produção automatizada de artigos e posts educativos sobre Estatística, Machine Learning e IA.*

![CI](https://img.shields.io/github/actions/workflow/status/SEU_USUARIO/NOME_DO_REPO/main.yml?branch=main)
![License](https://img.shields.io/github/license/SEU_USUARIO/NOME_DO_REPO)

---

## 📑 Índice
1. [Visão Geral](#visão-geral)  
2. [Arquitetura](#arquitetura)  
3. [Stack Tecnológico](#stack-tecnológico)  
4. [Estrutura do Repositório](#estrutura-do-repositório)  
5. [Pré-requisitos](#pré-requisitos)  
6. [Ambiente Local](#ambiente-local)  
7. [Infra-as-Code & GCP](#infra-as-code--gcp)  
8. [CI/CD](#cicd)  
9. [Como Usar](#como-usar)  
10. [Testes](#testes)  
11. [Roadmap](#roadmap)  
12. [Contribuição](#contribuição)  
13. [Licença](#licença)

---

## Visão Geral
Este projeto orquestra **agentes autônomos**—Planner, Writer, Reviewer, Illustrator, QA e Scheduler—para gerar, revisar e publicar:

* **1 artigo** principal e **5 posts** curtos por semana  
* Conteúdo **educativo** (estatística, ML e IA)  
* **Tons**: acessível, objetivo, sem informalidade excessiva  

Localmente você codifica, versiona e testa; no **GCP** você escala em produção usando Cloud Run, Cloud Scheduler, Pub/Sub e Secret Manager.

---

## Arquitetura
```mermaid
graph TD
    A(Planner) --> |temas| B(Writer)
    B --> |draft| C(Reviewer)
    C -- aprovado --> D(Illustrator)
    D --> |assets| E(QA)
    E --> |ok| F(Scheduler)
    F --> |API| G(LinkedIn)
    C -- rejeitado --> B
    G --> |engagement| A
````

* **Persistência**: planning.json em Firestore ou Cloud Storage
* **Mensageria**: Pub/Sub topics entre agentes
* **Escalonamento**: Cloud Scheduler dispara pipelines semanais
* **Observabilidade**: Cloud Logging + Error Reporting

---

## Stack Tecnológico

| Camada          | Tecnologia                               |
| --------------- | ---------------------------------------- |
| Linguagem       | Python 3.12                              |
| LLMs            | OpenAI API, Vertex AI Palm2 / Gemini     |
| Orquestração    | FastAPI + Pydantic (micro-services)      |
| Containerização | Docker + Docker Compose                  |
| CI/CD           | GitHub Actions → Cloud Build → Cloud Run |
| IaC             | Terraform (módulos GCP)                  |

---

## Estrutura do Repositório

```
.
├── agents/              # Planner, Writer, ...
├── config/              # config.yaml, secrets.toml.example
├── data/                # planning.json (dev)
├── docs/                # arquitetura, decisões ADR
├── notebooks/           # experimentos (opcional)
├── output/              # drafts & assets locais
├── scripts/             # run_pipeline.py, helpers
├── tests/               # pytest
├── Dockerfile
├── docker-compose.yml   # ambiente local completo
├── requirements.txt
└── .github/workflows/   # CI/CD
```

---

## Pré-requisitos

* **Docker 20+** e **docker-compose v2**
* **Python 3.12** se rodar sem Docker
* Conta GCP com projeto e faturamento
* Chaves de API OpenAI e Vertex AI
* Terraform 1.8+ (para IaC)
* [`gcloud`](https://cloud.google.com/sdk) CLI autenticado

---

## Ambiente Local

```bash
# 1. Clone
git clone https://github.com/SEU_USUARIO/NOME_DO_REPO.git
cd NOME_DO_REPO

# 2. Variáveis-ambiente
cp config/.env.example .env               # edite token OpenAI, etc.

# 3. Suba tudo em Docker
docker compose up --build

# 4. Rode a pipeline manualmente
docker compose exec api python scripts/run_pipeline.py
```

> **Dica:** adicione `--agent writer` ou `--dry-run` para executar etapas específicas.

---

## Infra-as-Code & GCP

### Provisionar com Terraform

```bash
cd infra/terraform
terraform init
terraform apply    # cria Cloud Run, Pub/Sub, Firestore, Secret Manager…
```

### Componentes Criados

| Serviço         | Descrição                         |
| --------------- | --------------------------------- |
| Cloud Run       | micro-serviços dos agentes        |
| Pub/Sub         | topics: `drafts`, `reviews`, …    |
| Cloud Scheduler | cron semanal `0 9 * * MON`        |
| Cloud Storage   | `gs://content-hub-assets`         |
| Secret Manager  | openai\_api\_key, vertex\_sa\_key |

---

## CI/CD

1. **Push → GitHub Actions**

   * Lint + Unit tests
   * Build Docker image
2. **Upload → Artifact Registry**
3. **Deploy → Cloud Run** via Cloud Build
4. **Tag semântica** (`v1.0.0`) cria release automática

Arquivo-exemplo: `.github/workflows/main.yml`.

---

## Como Usar

### Planejar (Planner)

```bash
curl -X POST http://localhost:8000/plan \
     -d '{"week":"2025-W23"}'
```

### Executar Writer

```bash
curl -X POST http://localhost:8000/write \
     -d '{"week":"2025-W23"}'
```

> **Produção**: endpoints expostos em Cloud Run; autentique com Identity-Aware Proxy ou Cloud Endpoints.

---

## Testes

```bash
pytest -q
```

Rodados automaticamente no CI. Cobertura mínima exigida: **80 %**.

---

## Roadmap

* [x] MVP local (pipeline síncrono)
* [ ] Agentes assíncronos via Pub/Sub
* [ ] Painel de métricas (Cloud Monitoring)
* [ ] Multi-idioma (EN / PT)
* [ ] Integração com Notion para planejamento

---

## Contribuição

1. Abra uma *issue* descrevendo mudança ou bug.
2. Crie branch `feature/<descrição>` a partir de `develop`.
3. Siga [Conventional Commits](https://www.conventionalcommits.org).
4. Envie *pull request*; o template solicitará checklist de testes.

---

## Licença

[MIT](LICENSE) © 2025 Seu Nome / Sua Empresa

```
```

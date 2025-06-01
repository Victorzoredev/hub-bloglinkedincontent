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

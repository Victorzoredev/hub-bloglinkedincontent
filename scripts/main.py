#!/usr/bin/env python3
"""
main.py: Executa head_agent, draft_agent e design_agent em sequência,
processando um ciclo completo do pipeline (criação de ficha, rascunho e HTML).
Uso: python3 main.py
"""

import subprocess
import sys

AGENTS = [
    "head_agent.py",
    "draft_agent.py",
    "design_agent.py",
    "post_blog.py",
    "post_person_linkedin.py"
]

def run_agent(script):
    cmd = [sys.executable, script]
    print(f"\n=== Executando: {' '.join(cmd)} ===")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao rodar {script}:", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(e.returncode)

def main():
    for script in AGENTS:
        run_agent(script)
    print("\n✅ Pipeline concluído!")

if __name__ == "__main__":
    main()

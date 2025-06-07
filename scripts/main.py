#!/usr/bin/env python3
"""
main.py: Executa head_agent, draft_agent e design_agent em sequência,
processando um ciclo completo do pipeline (criação de ficha, rascunho e HTML).
Uso: python3 main.py --lang en
"""
import argparse
import subprocess
import sys

AGENTS = [
    ("head_agent.py", []),     # Não precisa de argumentos
    ("draft_agent.py", []),    # Não precisa de argumentos
    ("design_agent.py", ["--lang"])  # Aceita argumento de língua
]

def run_agent(script, args=None):
    cmd = [sys.executable, script]
    if args:
        cmd.extend(args)
    print(f"\n=== Executando: {' '.join(cmd)} ===")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("Stderr:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] Falha ao rodar {script}.\nSaída:\n{e.stdout}\nErro:\n{e.stderr}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lang', type=str, default='en', help="Idioma do artigo/HTML (ex: en, pt)")
    args = parser.parse_args()

    for script, script_args in AGENTS:
        agent_args = []
        if script_args:
            # Para design_agent.py
            for sarg in script_args:
                if sarg == '--lang':
                    agent_args += [sarg, args.lang]
        run_agent(script, agent_args)

    print("\n✅ Pipeline concluído!")

if __name__ == "__main__":
    main()
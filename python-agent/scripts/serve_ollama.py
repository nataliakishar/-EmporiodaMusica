"""Inicia o runtime local em primeiro plano, sem alterar políticas do PowerShell.

Use outro terminal para o chat; Ctrl+C encerra o servidor.
"""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"


def main():
    executable = RUNTIME / "ollama" / "ollama.exe"
    if not executable.is_file():
        print("Runtime ausente. Conclua download_ollama.py e prepare_ollama.py.")
        return 2
    models = RUNTIME / "models"
    models.mkdir(exist_ok=True)
    environment = {**os.environ, "OLLAMA_MODELS": str(models), "OLLAMA_HOST": "127.0.0.1:11434",
                   "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1",
                   "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_CONTEXT_LENGTH": "4096"}
    try:
        return subprocess.call([str(executable), "serve"], env=environment, cwd=RUNTIME)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

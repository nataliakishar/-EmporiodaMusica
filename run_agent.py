"""Entrada executável a partir da raiz do desafio, sem instalação de pacotes."""

from pathlib import Path
import sys


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "python-agent"))
    from emporio_agent.cli import main

    raise SystemExit(main())

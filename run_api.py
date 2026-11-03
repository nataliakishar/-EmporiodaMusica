"""Inicia a API local; execute a partir da pasta do desafio."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'python-agent'))


def main():
    import uvicorn
    from emporio_agent.http_api import create_app

    parser = argparse.ArgumentParser(description='API local da Empório da Música')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    # Um processo: as sessões desta etapa ficam em memória, com expiração.
    uvicorn.run(create_app(), host='127.0.0.1', port=args.port, workers=1, access_log=False)


if __name__ == '__main__':
    main()

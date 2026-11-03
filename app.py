"""Entrada ASGI de produção para Vercel; a CLI e run_api.py permanecem locais."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'python-agent'))

from emporio_agent.cloud_runtime import make_cloud_service
from emporio_agent.http_api import create_app

app = create_app(make_cloud_service())

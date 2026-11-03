"""Configura as duas chaves do backend via stdin; nunca imprime seus valores."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emporio_agent.llm_config import LLMSettings
from emporio_agent.registration_store import RegistrationSettings

TEAM = 'biomatematica-1927s-projects'
PROJECT = 'prj_yhYWNfCQn8TpQItrQk04rwMFExDE'


def main():
    cli = shutil.which('vercel.cmd') or shutil.which('vercel')
    if not cli:
        raise RuntimeError('CLI Vercel não encontrada.')
    model, database = LLMSettings.load(), RegistrationSettings.load()
    if model.provider != 'groq' or not model.api_key:
        raise RuntimeError('Configure a chave Groq local antes do envio.')
    results = []
    for name, value in (('GROQ_API_KEY', model.api_key), ('SUPABASE_SECRET_KEY', database.secret_key)):
        # Nenhum valor secreto entra nos argumentos, no shell ou em arquivos novos.
        result = subprocess.run([cli, 'env', 'add', name, '--environment', 'production,preview',
                                 '--project', PROJECT, '--scope', TEAM, '--type', 'secret',
                                 '--yes', '--json'], input=value, capture_output=True,
                                text=True, timeout=90, cwd=ROOT.parent)
        results.append({'key': name, 'saved': result.returncode == 0, 'exit_code': result.returncode})
        if result.returncode:
            break  # Não publica stdout/stderr da CLI, que podem conter detalhes sensíveis.
    report = {'passed': len(results) == 2 and all(item['saved'] for item in results),
              'keys': results, 'project_id': PROJECT, 'values_printed': False}
    target = ROOT / '.runtime/vercel-secrets-setup.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Integração HTTP focada. Usa UMA pergunta real; não repete a suíte de conversas.

O cadastro sintético criado exige remoção administrativa por ID + marcador.
O relatório local registra o marcador para permitir limpeza mesmo após falha.
"""
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python-agent'))
from emporio_agent.config import resolve_data_dir
from emporio_agent.models import brl


def main():
    runtime = ROOT / 'python-agent/.runtime'
    runtime.mkdir(exist_ok=True)
    target = ROOT / 'python-agent/reports/api_live_validation.json'
    target.parent.mkdir(exist_ok=True)
    marker = uuid4().hex
    fixture = {'name': 'API Integration ' + marker, 'phone': '(85) 90000-0000',
               'email': 'api-' + marker + '@example.invalid', 'confirmed': True}
    report = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'fixture_name': fixture['name'], 'fixture_email': fixture['email'],
              'fixture_removed': False, 'remote_groq_questions': 0, 'checks': {}}

    def save():
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    save()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    opener = build_opener(ProxyHandler({}))
    sessions = []

    def call(method, path, payload=None, headers=None, timeout=300):
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = Request(base + path, data=data, headers={
            'Content-Type': 'application/json', **(headers or {})}, method=method)
        try:
            with opener.open(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def open_session():
        status, result = call('POST', '/sessions')
        assert status == 201, 'Não foi possível abrir sessão HTTP.'
        sid = result['session_id']
        headers = {'Authorization': 'Bearer ' + result['session_token']}
        sessions.append((sid, headers))
        return sid, headers

    with (runtime / 'api_live_server.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'run_api.py'), '--port', str(port)],
                                   cwd=ROOT, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 25
            while True:
                try:
                    status, health = call('GET', '/health', timeout=2)
                    assert status == 200 and health['status'] == 'ok'
                    break
                except (URLError, TimeoutError, OSError):
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('A API local não iniciou.') from None
                    time.sleep(0.2)
            report['checks']['http_health'] = True
            sid, headers = open_session()
            status, result = call('POST', f'/sessions/{sid}/messages',
                                  {'message': 'Quanto custa o Takamine GD20?'}, headers)
            assert status == 202 and result['code'] == 'registration_required'
            report['checks']['question_waits_for_registration'] = True
            report['remote_groq_questions'] = 1
            save()
            status, result = call('POST', f'/sessions/{sid}/registration', fixture, headers)
            if result.get('registration', {}).get('registration_id'):
                report['fixture_id'] = result['registration']['registration_id']
                save()
            assert status == 200, 'A resposta real não foi concluída; consulte o código seguro no relatório.'
            assert result['registration']['code'] == 'registration_saved'
            report['checks']['new_registration'] = True
            with (resolve_data_dir() / 'desafio_tecnico_ai_eng - products.csv').open(encoding='utf-8-sig', newline='') as handle:
                product = next(row for row in csv.DictReader(handle) if row['name'] == 'Takamine GD20 Dreadnought Natural')
            answer = result['answer']
            assert brl(Decimal(product['price_brl'])) in answer['text']
            assert product['status'] == 'active' and int(product['stock_quantity']) > 0
            assert answer['tools'] and answer['sources']
            assert all(fixture[k] not in answer['text'] for k in ('name', 'phone', 'email'))
            report['checks']['original_question_answered_with_csv_price_and_sources'] = True
            report['answer'] = answer
            # Novo atendimento com os mesmos contatos: consulta real de retorno, sem outra pergunta ao LLM.
            other, other_headers = open_session()
            status, existing = call('POST', f'/sessions/{other}/registration', fixture, other_headers)
            assert status == 200 and existing['registration']['code'] == 'registration_existing'
            assert 'registration_id' not in existing['registration']
            report['checks']['existing_contacts_recognized'] = True
            report['passed'] = True
        except Exception as error:
            report['error_type'] = type(error).__name__  # sem valores de entrada ou credenciais
        finally:
            for sid, headers in sessions:
                try:
                    call('DELETE', f'/sessions/{sid}', headers=headers, timeout=2)
                except Exception:
                    pass
            process.terminate()  # somente o processo iniciado por este script
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            report['owned_server_stopped'] = process.poll() is not None
            save()
    print(json.dumps({key: report.get(key) for key in
                      ('passed', 'checks', 'remote_groq_questions', 'fixture_id', 'fixture_removed', 'owned_server_stopped', 'error_type')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

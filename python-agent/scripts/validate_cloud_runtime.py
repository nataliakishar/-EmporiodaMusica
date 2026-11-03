"""Somente a persistência cloud nova; --live testa RPCs, sem modelo/cadastro reais."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from emporio_agent.api_sessions import APIError
from emporio_agent.cloud_runtime import CloudRPC, CloudSessionService
from test_cloud_runtime import AgentDouble, StoreDouble
from test_http_api import APITests


def live_check():
    store = StoreDouble()
    a = CloudSessionService(CloudRPC(), AgentDouble, store_factory=lambda: store)
    b = CloudSessionService(CloudRPC(), AgentDouble, store_factory=lambda: store)
    created = a.create()
    sid, token = created['session_id'], created['session_token']
    result = {'passed': False, 'synthetic_session_id': sid, 'groq_calls': 0, 'customer_writes': 0}
    try:
        assert a.message(sid, token, 'Primeira')['code'] == 'registration_required'
        response = b.register(sid, token, confirmed=True, name='Pessoa Sintetica Cloud',
                              phone='(85) 90000-0000', email='cloud-live@example.invalid')
        assert 'Turnos anteriores: 0' in response['answer']['text']
        assert 'Turnos anteriores: 1' in a.message(sid, token, 'Continuação')['answer']['text']
        result['cross_instance_history'] = True
        with a.access(sid, token):
            try:
                b.message(sid, token, 'Concorrente')
                raise AssertionError('Sem exclusão mútua.')
            except APIError as error:
                assert error.status == 409
        result['distributed_lock'] = True
        try:
            b.message(sid, 'incorrect', 'Sem acesso')
            raise AssertionError('Token inválido aceito.')
        except APIError as error:
            assert error.status == 404
        result['token_isolation'] = True
        b.clear(sid, token)
        assert 'Turnos anteriores: 0' in a.message(sid, token, 'Novo contexto')['answer']['text']
        result['clear_preserves_registration'] = len(store.calls) == 1
        result['passed'] = True
    finally:
        b.close(sid, token)
        result['session_removed'] = True
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_cloud_runtime.py')
    for name in ('test_health_and_docs_without_credentials_or_external_calls',
                 'test_explicit_cancellation_closes_without_db_or_model',
                 'test_close_discards_conversation_without_db_operation',
                 'test_clear_keeps_registration_and_releases_pending_question'):
        suite.addTest(APITests(name))
    log = io.StringIO()
    tested = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    report = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'tests': {'run': tested.testsRun, 'failures': len(tested.failures), 'errors': len(tested.errors)},
              'passed': tested.wasSuccessful(), 'groq_calls': 0}
    if args.live and tested.wasSuccessful():
        report['live'] = live_check()
        report['passed'] = report['live']['passed']
    previous = json.loads((ROOT / 'reports/api_validation.json').read_text(encoding='utf-8'))
    report['original_sources_unchanged'] = all(
        hashlib.sha256((ROOT.parent / 'data' / name).read_bytes()).hexdigest() == value
        for name, value in previous['source_sha256_after'].items())
    core = ('agent.py', 'tools.py', 'policies.py', 'policy_calculations.py', 'policy_guards.py', 'llm.py')
    digest = hashlib.sha256(b''.join((ROOT / 'emporio_agent' / name).read_bytes() for name in core)).hexdigest()
    report['agent_core_unchanged'] = digest == previous['core_implementation_sha256']
    report['passed'] &= report['original_sources_unchanged'] and report['agent_core_unchanged']
    (ROOT / 'reports/cloud_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'reports/cloud_tests.txt').write_text(log.getvalue(), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    if not tested.wasSuccessful():
        print(log.getvalue())
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

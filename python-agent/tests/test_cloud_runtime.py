"""Somente persistência e fontes privadas adicionadas para publicação."""
import base64
from collections import deque
from copy import deepcopy
import hashlib
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from emporio_agent.agent import Answer
from emporio_agent.api_sessions import APIError
from emporio_agent.cloud_runtime import CloudRPC, CloudSessionService, PrivateAssets
from emporio_agent.data import FILENAMES
from emporio_agent.http_api import create_app
from emporio_agent.llm import LLMError
from emporio_agent.policies import FILENAME
from emporio_agent.registration import RegistrationError


class MemoryRPC:
    def __init__(self):
        self.rows = {}
        self.fail_finish = False

    def call(self, name, p):
        sid = p['p_id']
        if name == 'agent_session_create':
            self.rows[sid] = {'hash': p['p_hash'], 'lease': None, 'state': {}}
            return {'code': 'created'}
        row = self.rows.get(sid)
        if name == 'agent_session_acquire':
            if not row or row['hash'] != p['p_hash']:
                return {'code': 'not_found'}
            if row['lease']:
                return {'code': 'busy'}
            row['lease'] = p['p_lease']
            return {'code': 'acquired', 'state': deepcopy(row['state'])}
        if name == 'agent_session_finish':
            if self.fail_finish or not row or row['lease'] != p['p_lease']:
                return False
            if p['p_close']:
                del self.rows[sid]
            else:
                row.update(state=deepcopy(p['p_state']), lease=None)
            return True
        raise AssertionError(name)


class AgentDouble:
    error = None

    def __init__(self):
        self.turns, self.references = deque(maxlen=6), {}

    def ask(self, question):
        if type(self).error:
            raise type(self).error
        text = f'Turnos anteriores: {len(self.turns)}. Pergunta: {question}'
        self.turns.append([{'role': 'user', 'content': question}, {'role': 'assistant', 'content': text}])
        self.references = {'product_ids': [95]}
        return Answer(text, ['buscar_modelo'], [])

    def reset(self):
        self.turns.clear()
        self.references.clear()


class StoreDouble:
    def __init__(self):
        self.calls, self.error = [], None

    def resolve(self, draft):
        self.calls.append(draft.id)
        if self.error:
            raise self.error
        return {'code': 'registration_saved', 'message': 'Conferido.', 'registration_id': draft.id}


class CloudTests(unittest.TestCase):
    def setUp(self):
        AgentDouble.error = None
        self.rpc, self.store = MemoryRPC(), StoreDouble()
        self.a = CloudSessionService(self.rpc, AgentDouble, store_factory=lambda: self.store)
        self.b = CloudSessionService(self.rpc, AgentDouble, store_factory=lambda: self.store)
        self.created = self.a.create()
        self.sid, self.token = self.created['session_id'], self.created['session_token']
        self.contacts = {'confirmed': True, 'name': 'Pessoa Sintetica Cloud',
                         'phone': '(85) 90000-0000', 'email': 'cloud-test@example.invalid'}

    def register(self, service=None):
        return (service or self.b).register(self.sid, self.token, **self.contacts)

    def test_other_instance_resumes_pending_and_history(self):
        self.assertEqual(self.a.message(self.sid, self.token, 'Primeira')['code'], 'registration_required')
        result = self.register()
        self.assertIn('Turnos anteriores: 0. Pergunta: Primeira', result['answer']['text'])
        result = self.a.message(self.sid, self.token, 'Continuação')
        self.assertIn('Turnos anteriores: 1', result['answer']['text'])
        self.assertEqual(len(self.store.calls), 1)

    def test_invalid_token_cannot_read_or_change_state(self):
        with self.assertRaises(APIError) as caught:
            self.b.message(self.sid, 'incorrect', 'Inválida')
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.rpc.rows[self.sid]['state'], {})

    def test_distributed_lease_prevents_concurrent_requests(self):
        with self.a.access(self.sid, self.token):
            with self.assertRaises(APIError) as caught:
                self.b.message(self.sid, self.token, 'Concorrente')
            self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.b.message(self.sid, self.token, 'Depois')['code'], 'registration_required')

    def test_registration_failure_preserves_draft_uuid_across_instances(self):
        self.store.error = RegistrationError('temporary')
        with self.assertRaises(APIError):
            self.register(self.a)
        self.store.error = None
        self.register(self.b)
        self.assertEqual(self.store.calls[0], self.store.calls[1])
        self.assertIsNone(self.rpc.rows[self.sid]['state']['draft'])

    def test_model_failure_keeps_confirmation_and_original_question(self):
        self.a.message(self.sid, self.token, 'Pendente')
        AgentDouble.error = LLMError('secret-must-not-leak')
        with self.assertRaises(APIError) as caught:
            self.register()
        self.assertTrue(caught.exception.payload['registration_confirmed'])
        self.assertNotIn('secret-must-not-leak', str(caught.exception.payload))
        AgentDouble.error = None
        result = self.a.message(self.sid, self.token, 'Pendente')
        self.assertEqual(result['code'], 'answered')
        self.assertEqual(len(self.store.calls), 1)

    def test_clear_and_close_work_after_changing_instance(self):
        self.register()
        self.a.message(self.sid, self.token, 'Primeira')
        self.b.clear(self.sid, self.token)
        self.assertIn('Turnos anteriores: 0', self.a.message(self.sid, self.token, 'Nova')['answer']['text'])
        self.b.close(self.sid, self.token)
        self.assertNotIn(self.sid, self.rpc.rows)

    def test_http_health_and_cancellation_do_not_require_model(self):
        client = TestClient(create_app(self.b))
        self.assertEqual(client.get('/health').json()['session_storage'], 'supabase')
        response = client.post(f'/sessions/{self.sid}/registration', json={'confirmed': False},
                               headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.sid, self.rpc.rows)
        self.assertEqual(self.store.calls, [])

    def test_failure_to_save_is_not_reported_as_success(self):
        self.rpc.fail_finish = True
        with self.assertRaises(APIError) as caught:
            self.a.message(self.sid, self.token, 'Oi')
        self.assertEqual(caught.exception.payload['code'], 'state_not_saved')

    def test_sources_reject_missing_files_and_invalid_hash(self):
        files = {name: {'base64': base64.b64encode(b'synthetic').decode(), 'sha256': 'bad'}
                 for name in list(FILENAMES.values()) + [FILENAME]}
        class AssetsRPC:
            def call(self, *args):
                return {'files': files}
        with self.assertRaises(APIError):
            PrivateAssets(AssetsRPC()).data_dir()
        files.clear()
        with self.assertRaises(APIError):
            PrivateAssets(AssetsRPC()).data_dir()

    def test_rpc_allowlist_and_sanitized_transport_errors(self):
        rpc = CloudRPC(settings_factory=lambda: (_ for _ in ()).throw(ValueError('SECRET')))
        for name in ('arbitrary_sql', 'agent_assets_get'):
            with self.subTest(name=name), self.assertRaises(APIError) as caught:
                rpc.call(name, {})
            self.assertNotIn('SECRET', str(caught.exception.payload))


if __name__ == '__main__':
    unittest.main()

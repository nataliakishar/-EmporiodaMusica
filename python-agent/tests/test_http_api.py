"""Apenas os novos fluxos HTTP, com dependências externas substituídas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest

from fastapi.testclient import TestClient

from emporio_agent.agent import Answer
from emporio_agent.api_sessions import SessionService
from emporio_agent.http_api import create_app
from emporio_agent.llm import LLMError, RateLimitError
from emporio_agent.registration import RegistrationError


CONTACTS = {'name': 'Pessoa Sintetica HTTP', 'phone': '(85) 90000-0000',
            'email': 'api-test@example.invalid', 'confirmed': True}


class FakeAgent:
    def __init__(self):
        self.questions = []
        self.error = None
        self.clears = 0
        self.entered = None
        self.release = None

    def ask(self, question):
        if self.entered:
            self.entered.set()
            if not self.release.wait(5):
                raise AssertionError('Timeout no teste de concorrência.')
        if self.error:
            raise self.error
        self.questions.append(question)
        return Answer('Resposta de teste sem dados cadastrais.', ['buscar_modelo'], [{'filename': 'products.csv'}])

    def reset(self):
        self.questions.clear()
        self.clears += 1


class FakeStore:
    def __init__(self):
        self.calls = []
        self.error = None
        self.existing = False

    def resolve(self, draft):
        self.calls.append(draft)
        if self.error:
            raise self.error
        if self.existing:
            return {'code': 'registration_existing', 'message': 'Obrigado por retornar!'}
        return {'code': 'registration_saved', 'message': 'Obrigado pelas informações!', 'registration_id': draft.id}


class APITests(unittest.TestCase):
    def setUp(self):
        self.agents = []
        self.store = FakeStore()
        self.now = 0

        def factory():
            agent = FakeAgent()
            self.agents.append(agent)
            return agent

        self.service = SessionService(factory, lambda: self.store, clock=lambda: self.now, ttl=60, capacity=3)
        self.client = TestClient(create_app(self.service))
        self.sid, self.headers = self.open()

    def open(self):
        response = self.client.post('/sessions')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('LGPD', data['privacy_notice'])
        return data['session_id'], {'Authorization': 'Bearer ' + data['session_token']}

    def send(self, message='Quanto custa o Takamine GD20?', sid=None, headers=None):
        return self.client.post(f'/sessions/{sid or self.sid}/messages',
                                json={'message': message}, headers=headers or self.headers)

    def register(self, contacts=None, sid=None, headers=None):
        return self.client.post(f'/sessions/{sid or self.sid}/registration',
                                json=contacts if contacts is not None else CONTACTS, headers=headers or self.headers)

    def test_health_and_docs_without_credentials_or_external_calls(self):
        self.assertEqual(self.client.get('/health').json()['status'], 'ok')
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertIn('/sessions/{session_id}/registration', self.client.get('/openapi.json').json()['paths'])
        self.assertEqual((self.agents, self.store.calls), ([], []))

    def test_question_waits_for_registration_without_model(self):
        response = self.send()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['code'], 'registration_required')
        self.assertNotIn('session_token', response.text)
        self.assertEqual((self.agents, self.store.calls), ([], []))

    def test_new_registration_resumes_original_question(self):
        self.send()
        result = self.register().json()
        self.assertEqual(result['code'], 'answered')
        self.assertEqual(result['registration']['code'], 'registration_saved')
        self.assertEqual(self.agents[0].questions, ['Quanto custa o Takamine GD20?'])
        self.assertEqual(len(self.store.calls), 1)
        self.assertEqual(self.store.calls[0].phone, '+5585900000000')
        for key in ('name', 'phone', 'email'):
            self.assertNotIn(CONTACTS[key], str(self.agents[0].questions) + str(result))
        self.assertEqual(result['answer']['tools'], ['buscar_modelo'])

    def test_existing_contacts_acknowledged_without_exposing_profile(self):
        self.store.existing = True
        self.send()
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['registration']['code'], 'registration_existing')
        self.assertNotIn('registration_id', response.text)
        self.assertEqual(len(self.agents[0].questions), 1)

    def test_followup_uses_same_agent_without_recollecting_contacts(self):
        self.register()
        self.send('Pergunta inicial')
        self.send('Esse produto está disponível?')
        self.assertEqual(len(self.agents), 1)
        self.assertEqual(len(self.store.calls), 1)
        self.assertEqual(len(self.agents[0].questions), 2)

    def test_registration_before_question_does_not_call_model(self):
        response = self.register()
        self.assertEqual(response.json()['code'], 'registration_confirmed')
        self.assertEqual(self.agents, [])
        self.assertEqual(self.send().status_code, 200)

    def test_explicit_cancellation_closes_without_db_or_model(self):
        self.send()
        self.assertEqual(self.register({'confirmed': False}).json()['code'], 'session_closed')
        self.assertEqual(self.send().status_code, 404)
        self.assertEqual((self.agents, self.store.calls), ([], []))

    def test_registration_replay_does_not_repeat_write_or_answer(self):
        self.send()
        self.register()
        self.assertEqual(self.register().json()['code'], 'registration_confirmed')
        self.assertEqual(len(self.store.calls), 1)
        self.assertEqual(len(self.agents[0].questions), 1)

    def test_first_pending_question_is_preserved(self):
        self.send('Primeira pergunta')
        self.assertEqual(self.send('Outra pergunta').status_code, 409)
        self.assertEqual(self.send('Primeira pergunta').status_code, 202)
        self.register()
        self.assertEqual(self.agents[0].questions, ['Primeira pergunta'])

    def test_database_failure_never_releases_gate_and_retry_reuses_uuid(self):
        self.send()
        self.store.error = RegistrationError('secretkey-or-contact-must-not-leak')
        response = self.register()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secretkey-or-contact', response.text)
        self.assertEqual(self.agents, [])
        self.assertEqual(self.send().status_code, 202)
        self.store.error = None
        self.assertEqual(self.register().status_code, 200)
        self.assertEqual(self.store.calls[0].id, self.store.calls[1].id)

    def test_uncertain_registration_rejects_changed_contacts(self):
        self.store.error = RegistrationError('temporary')
        self.register()
        self.assertEqual(self.register({**CONTACTS, 'email': 'changed@example.invalid'}).status_code, 409)
        self.assertEqual(len(self.store.calls), 1)

    def test_model_failure_after_registration_keeps_pending_and_no_second_write(self):
        self.register()
        agent = FakeAgent()
        agent.error = LLMError('SECRET must not be returned')
        self.service.sessions[self.sid].agent = agent
        response = self.send()
        self.assertEqual(response.status_code, 502)
        self.assertTrue(response.json()['registration_confirmed'])
        self.assertNotIn('SECRET', response.text)
        self.assertEqual(self.send('Outra').status_code, 409)
        agent.error = None
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(len(self.store.calls), 1)

    def test_quota_error_has_safe_retry_header(self):
        self.register()
        agent = FakeAgent()
        agent.error = RateLimitError(30)
        self.service.sessions[self.sid].agent = agent
        response = self.send()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['retry-after'], '30')

    def test_missing_and_other_session_tokens_cannot_access(self):
        other, headers = self.open()
        self.assertEqual(self.client.post(f'/sessions/{self.sid}/messages', json={'message': 'Oi'}).status_code, 401)
        self.assertEqual(self.send(sid=other).status_code, 404)
        self.assertEqual(self.register(sid=other).status_code, 404)
        self.assertEqual(self.client.delete(f'/sessions/{other}', headers=self.headers).status_code, 404)
        self.assertEqual(self.send(sid=other, headers=headers).status_code, 202)

    def test_sessions_have_isolated_agents_and_registration(self):
        self.register()
        self.send('Sessão A')
        other, headers = self.open()
        self.assertEqual(self.send('Sessão B', other, headers).status_code, 202)
        self.register(sid=other, headers=headers)
        self.assertEqual(self.agents[0].questions, ['Sessão A'])
        self.assertEqual(self.agents[1].questions, ['Sessão B'])

    def test_clear_keeps_registration_and_releases_pending_question(self):
        self.register()
        self.send()
        response = self.client.post(f'/sessions/{self.sid}/clear', headers=self.headers)
        self.assertTrue(response.json()['registration_confirmed'])
        self.assertEqual(self.agents[0].clears, 1)
        self.assertEqual(self.send('Novo assunto').status_code, 200)
        self.assertEqual(len(self.store.calls), 1)

    def test_clear_before_registration_does_not_bypass_gate(self):
        self.send('Primeira')
        self.client.post(f'/sessions/{self.sid}/clear', headers=self.headers)
        self.assertEqual(self.send('Outra').status_code, 202)
        self.assertEqual(self.agents, [])

    def test_close_discards_conversation_without_db_operation(self):
        self.register()
        self.assertEqual(self.client.delete(f'/sessions/{self.sid}', headers=self.headers).status_code, 200)
        self.assertEqual(self.send().status_code, 404)
        self.assertEqual(len(self.store.calls), 1)

    def test_expiration_and_capacity(self):
        self.open()
        self.open()
        self.assertEqual(self.client.post('/sessions').status_code, 503)
        self.now = 61
        self.assertEqual(self.send().status_code, 404)
        self.open()
        self.assertEqual(len(self.service.sessions), 1)

    def test_concurrent_request_is_rejected_but_other_session_still_works(self):
        self.register()
        agent = FakeAgent()
        agent.entered, agent.release = Event(), Event()
        self.service.sessions[self.sid].agent = agent
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.send)
            try:
                self.assertTrue(agent.entered.wait(5))
                self.assertEqual(self.send().status_code, 409)
                other, headers = self.open()
                self.assertEqual(self.send('Outra sessão', other, headers).status_code, 202)
                self.now = 61
                self.assertEqual(self.send().status_code, 409)  # não expira operação em andamento
            finally:
                agent.release.set()
            self.assertEqual(future.result(timeout=5).status_code, 200)

    def test_invalid_and_extra_fields_never_echo_personal_data(self):
        cases = [
            {'confirmed': 'true', 'email': 'private-value@example.invalid'},
            {**CONTACTS, 'registered': True},
            {**CONTACTS, 'email': 'sensitive@example.invalid' * 40},
            {'confirmed': True},
            {**CONTACTS, 'phone': 'sensitive-invalid-contact'},
        ]
        for body in cases:
            with self.subTest(body_keys=list(body)):
                response = self.register(body)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn('sensitive', response.text)
                self.assertNotIn('private-value', response.text)
                self.assertNotIn('input', response.json())
        self.assertEqual((self.agents, self.store.calls), ([], []))

    def test_message_validation_json_errors_and_body_limit(self):
        for body in ({'message': ''}, {'message': '   '}, {'message': 'x' * 4001},
                     {'message': 12}, {'message': 'Oi', 'registered': True}):
            response = self.client.post(f'/sessions/{self.sid}/messages', headers=self.headers, json=body)
            self.assertEqual(response.status_code, 422)
        invalid = self.client.post(f'/sessions/{self.sid}/messages', headers={**self.headers, 'Content-Type': 'application/json'}, content='{invalid-private')
        self.assertEqual(invalid.status_code, 422)
        self.assertNotIn('invalid-private', invalid.text)
        large = self.client.post('/sessions', content=b'x' * 32769)
        self.assertEqual(large.status_code, 413)
        self.assertEqual(large.headers['cache-control'], 'no-store')

    def test_cors_security_headers_and_safe_not_found(self):
        headers = {'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'POST',
                   'Access-Control-Request-Headers': 'authorization,content-type'}
        response = self.client.options('/sessions', headers=headers)
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:3000')
        denied = self.client.options('/sessions', headers={**headers, 'Origin': 'https://untrusted.invalid'})
        self.assertNotIn('access-control-allow-origin', denied.headers)
        response = self.client.get('/unknown-private')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('unknown-private', response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
        with self.assertRaises(ValueError):
            create_app(allowed_origins=['*'])


if __name__ == '__main__':
    unittest.main()

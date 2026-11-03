"""API real com fronteiras externas substituídas, exclusiva dos testes da UI.

Não lê .env, não conecta à Groq/Supabase e não altera dados originais.
"""
from pathlib import Path
import sys
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python-agent'))

import uvicorn
from emporio_agent.agent import Answer
from emporio_agent.api_sessions import SessionService
from emporio_agent.conversation_registration import NEW_MESSAGE, RETURNING_MESSAGE
from emporio_agent.http_api import create_app


class TestAgent:
    def __init__(self):
        self.turns = []

    def ask(self, question):
        self.turns.append(question)
        return Answer('Resposta de teste da interface. Sua pergunta foi: ' + question,
                      ['buscar_modelo'], [{'files': ['desafio_tecnico_ai_eng - products.csv']}])

    def reset(self):
        self.turns.clear()


class TestStore:
    def __init__(self):
        self.contacts = set()
        self.lock = Lock()

    def resolve(self, draft):
        pair = (draft.phone, draft.email)
        with self.lock:
            if pair in self.contacts:
                return {'code': 'registration_existing', 'message': RETURNING_MESSAGE}
            self.contacts.add(pair)
            return {'code': 'registration_saved', 'message': NEW_MESSAGE, 'registration_id': draft.id}


if __name__ == '__main__':
    store = TestStore()
    app = create_app(SessionService(TestAgent, lambda: store), allowed_origins=['http://127.0.0.1:3100'])
    uvicorn.run(app, host='127.0.0.1', port=8765, access_log=False)

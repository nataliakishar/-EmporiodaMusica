"""Sessões locais da API; reutiliza o agente e o cadastro sem alterar suas regras."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import secrets
from threading import Lock
from time import monotonic
from uuid import uuid4

from .agent import ConversationAgent
from .config import resolve_data_dir
from .conversation_registration import ConversationRegistrationStore, PRIVACY_NOTICE
from .llm import ChatModel, RateLimitError
from .llm_config import LLMSettings
from .registration import RegistrationDraft, RegistrationError
from .registration_store import RegistrationSettings


class APIError(Exception):
    def __init__(self, status, code, message, **details):
        self.status = status
        self.payload = {'code': code, 'message': message, **details}


def make_agent():
    return ConversationAgent(ChatModel(LLMSettings.load()), resolve_data_dir())


def make_registration_store():
    return ConversationRegistrationStore(RegistrationSettings.load())


@dataclass(repr=False)
class Session:
    token_hash: bytes
    touched: float
    lock: object = field(default_factory=Lock)
    registered: bool = False
    pending: str | None = None
    draft: RegistrationDraft | None = None
    agent: object = None
    registration: dict | None = None


class SessionService:
    """Memória de um único processo. Não autentica clientes nem pedidos."""
    storage = 'memory'
    def __init__(self, agent_factory=make_agent, store_factory=make_registration_store,
                 *, ttl=1800, capacity=100, clock=monotonic):
        self.agent_factory, self.store_factory = agent_factory, store_factory
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self.sessions = {}
        self.lock = Lock()

    def _purge(self):
        expired = [sid for sid, s in self.sessions.items()
                   if not s.lock.locked() and self.clock() - s.touched >= self.ttl]
        for sid in expired:
            del self.sessions[sid]

    def discard(self, sid):
        del self.sessions[sid]

    def create(self):
        with self.lock:
            self._purge()
            if len(self.sessions) >= self.capacity:
                raise APIError(503, 'session_capacity', 'Há muitos atendimentos abertos. Tente mais tarde.')
            sid, token = str(uuid4()), secrets.token_urlsafe(32)
            self.sessions[sid] = Session(hashlib.sha256(token.encode()).digest(), self.clock())
        return {'session_id': sid, 'session_token': token, 'expires_in_seconds': self.ttl,
                'code': 'registration_required', 'privacy_notice': PRIVACY_NOTICE,
                'message': 'Olá! Bem-vindo à Empório da Música. Como posso ajudar?',
                'required_fields': ['name', 'phone', 'email']}

    @contextmanager
    def access(self, sid, token):
        if not token:
            raise APIError(401, 'session_token_required', 'Informe o token da sessão no cabeçalho Authorization: Bearer.')
        with self.lock:
            self._purge()
            session = self.sessions.get(sid)
            if session is None or not secrets.compare_digest(
                    session.token_hash, hashlib.sha256(token.encode()).digest()):
                raise APIError(404, 'session_not_found', 'Sessão inexistente ou expirada. Abra um novo atendimento.')
            if not session.lock.acquire(blocking=False):
                raise APIError(409, 'session_busy', 'Aguarde a conclusão da solicitação anterior desta sessão.')
        try:
            yield session
        finally:
            with self.lock:
                session.touched = self.clock()
                session.lock.release()

    def _answer(self, session):
        try:
            if session.agent is None:
                session.agent = self.agent_factory()
            answer = session.agent.ask(session.pending)
        except RateLimitError as error:
            details = {'registration_confirmed': True, 'pending_message_saved': True}
            if isinstance(error.retry_after, (int, float)) and 0 <= error.retry_after <= 3600:
                details['retry_after_seconds'] = int(error.retry_after)
            raise APIError(429, 'provider_rate_limit', 'O provedor atingiu sua cota. Aguarde e repita a pergunta.', **details) from None
        except Exception:
            # Não devolve mensagens de exceção: podem conter caminhos, chaves ou dados.
            raise APIError(502, 'answer_unavailable', 'Não foi possível responder agora. Repita a mesma pergunta.',
                           registration_confirmed=True, pending_message_saved=True) from None
        session.pending = None
        return {'code': 'answered', 'answer': asdict(answer), 'registration_confirmed': True}

    def message(self, sid, token, message):
        with self.access(sid, token) as session:
            if session.pending is not None and session.pending != message:
                raise APIError(409, 'pending_message', 'Há uma pergunta pendente. Conclua o cadastro, repita a pergunta original ou limpe o contexto.')
            session.pending = message
            if not session.registered:
                return {'code': 'registration_required', 'message': PRIVACY_NOTICE,
                        'required_fields': ['name', 'phone', 'email'], 'pending_message_saved': True}
            return self._answer(session)

    def register(self, sid, token, *, confirmed, name=None, phone=None, email=None):
        with self.access(sid, token) as session:
            if not confirmed:
                with self.lock:
                    self.discard(sid)
                return {'code': 'session_closed', 'message': 'Atendimento encerrado. Nenhum cadastro foi enviado nesta solicitação.'}
            if not session.registered:
                try:
                    draft = RegistrationDraft.prepare(name, phone, email)
                except RegistrationError:
                    raise APIError(422, 'invalid_registration', 'Confira nome, telefone brasileiro com DDD e e-mail antes de confirmar.') from None
                # Repetições de uma gravação incerta usam o mesmo UUID e os mesmos contatos.
                if session.draft is not None and (
                        session.draft.name, session.draft.phone, session.draft.email
                ) != (draft.name, draft.phone, draft.email):
                    raise APIError(409, 'registration_retry', 'Repita os mesmos dados para conferir o envio anterior ou encerre a sessão.')
                session.draft = session.draft or draft
                try:
                    result = self.store_factory().resolve(session.draft)
                    if result.get('code') not in {'registration_saved', 'registration_existing'}:
                        raise RegistrationError('Resultado inválido.')
                except Exception:
                    raise APIError(502, 'registration_unavailable', 'Não foi possível confirmar o cadastro. Repita o envio; o atendimento ainda não foi liberado.') from None
                session.registration = result
                session.registered, session.draft = True, None
            response = {'code': 'registration_confirmed', 'registration': session.registration,
                        'registration_confirmed': True}
            if session.pending is not None:
                response.update(self._answer(session))
            return response

    def clear(self, sid, token):
        with self.access(sid, token) as session:
            if session.agent is not None:
                session.agent.reset()
            session.pending = None
            return {'code': 'context_cleared', 'registration_confirmed': session.registered,
                    'message': 'Conversa reiniciada. Como posso ajudar?'}

    def close(self, sid, token):
        with self.access(sid, token):
            with self.lock:
                self.discard(sid)
        return {'code': 'session_closed', 'message': 'Atendimento encerrado. O cadastro na loja foi preservado.'}

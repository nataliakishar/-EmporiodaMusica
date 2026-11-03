"""Estado compartilhado e fontes privadas para funções Python na nuvem."""
import base64
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
from threading import Lock
from urllib.request import Request, build_opener
from uuid import UUID, uuid4

from .agent import ConversationAgent
from .api_sessions import APIError, Session, SessionService
from .conversation_registration import PRIVACY_NOTICE
from .data import FILENAMES
from .llm import ChatModel
from .llm_config import LLMSettings
from .policies import FILENAME
from .registration import RegistrationDraft
from .registration_store import NoRegistrationRedirects, RegistrationSettings


class CloudRPC:
    """Somente RPCs fixas, autenticadas pelo backend; nunca aceita SQL do cliente."""
    ALLOWED = {'agent_session_create', 'agent_session_acquire', 'agent_session_finish',
               'agent_assets_get', 'agent_assets_set'}

    def __init__(self, settings_factory=RegistrationSettings.load, opener=None):
        self.settings_factory = settings_factory
        self.opener = opener or build_opener(NoRegistrationRedirects())

    def call(self, name, payload):
        if name not in self.ALLOWED:
            raise APIError(503, 'cloud_unavailable', 'Operação de nuvem indisponível.')
        try:
            settings = self.settings_factory()
            request = Request(settings.url + '/rest/v1/rpc/' + name,
                              data=json.dumps(payload, ensure_ascii=False).encode(),
                              headers={'apikey': settings.secret_key, 'Content-Type': 'application/json'}, method='POST')
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ValueError('Resposta excedida.')
                return json.loads(raw)
        except Exception:
            raise APIError(503, 'cloud_unavailable', 'Não foi possível confirmar o estado do atendimento. Aguarde e tente novamente.') from None


class PrivateAssets:
    """Baixa o snapshot protegido para o diretório temporário do servidor, com SHA-256."""
    def __init__(self, rpc):
        self.rpc, self.lock, self.path = rpc, Lock(), None

    def data_dir(self):
        with self.lock:
            if self.path is not None and self.path.is_dir():
                return self.path
            bundle = self.rpc.call('agent_assets_get', {})
            expected = set(FILENAMES.values()) | {FILENAME}
            if not isinstance(bundle, dict) or set(bundle.get('files', {})) != expected:
                raise APIError(503, 'sources_unavailable', 'As fontes do atendimento ainda não foram configuradas.')
            decoded = {}
            try:
                for name, entry in bundle['files'].items():
                    content = base64.b64decode(entry['base64'], validate=True)
                    if len(content) > 500_000 or hashlib.sha256(content).hexdigest() != entry['sha256']:
                        raise ValueError('Hash inválido.')
                    decoded[name] = content
            except (ValueError, KeyError, TypeError):
                raise APIError(503, 'sources_unavailable', 'Não foi possível verificar as fontes do atendimento.') from None
            directory = Path(tempfile.mkdtemp(prefix='emporio-agent-'))
            for name, content in decoded.items():
                (directory / name).write_bytes(content)
            self.path = directory
            return directory


class RestoredAgent:
    """Restaura apenas os seis turnos e referências; não serializa objetos Python."""
    def __init__(self, factory, state):
        self.factory, self.state, self.agent = factory, deepcopy(state), None

    def ask(self, question):
        if self.agent is None:
            self.agent = self.factory()
            self.agent.turns.extend(self.state.get('turns', [])[-6:])
            self.agent.references = self.state.get('references', {})
        return self.agent.ask(question)

    def reset(self):
        self.state = {}
        if self.agent is not None:
            self.agent.reset()

    def export(self):
        if self.agent is None:
            return self.state
        return {'turns': list(self.agent.turns), 'references': self.agent.references}


class CloudSessionService(SessionService):
    storage = 'supabase'

    def __init__(self, rpc, agent_factory, **kwargs):
        super().__init__(agent_factory, **kwargs)
        self.rpc = rpc
        self.current = ContextVar('emporio_cloud_session')

    def create(self):
        sid, token = str(uuid4()), secrets.token_urlsafe(32)
        result = self.rpc.call('agent_session_create', {
            'p_id': sid, 'p_hash': hashlib.sha256(token.encode()).hexdigest()})
        if not isinstance(result, dict) or result.get('code') != 'created':
            raise APIError(503, 'session_capacity', 'Não foi possível abrir outra conversa. Tente mais tarde.')
        return {'session_id': sid, 'session_token': token, 'expires_in_seconds': 1800,
                'code': 'registration_required', 'privacy_notice': PRIVACY_NOTICE,
                'message': 'Olá! Bem-vindo à Empório da Música. Como posso ajudar?',
                'required_fields': ['name', 'phone', 'email']}

    def discard(self, sid):
        context = self.current.get()
        if context['id'] != sid:
            raise APIError(404, 'session_not_found', 'Sessão inexistente ou expirada.')
        context['closed'] = True

    @contextmanager
    def access(self, sid, token):
        if not token:
            raise APIError(401, 'session_token_required', 'Informe o token da sessão no cabeçalho Authorization: Bearer.')
        try:
            sid = str(UUID(sid))
        except (ValueError, AttributeError):
            raise APIError(404, 'session_not_found', 'Sessão inexistente ou expirada.') from None
        lease = str(uuid4())
        digest = hashlib.sha256(token.encode()).hexdigest()
        result = self.rpc.call('agent_session_acquire', {'p_id': sid, 'p_hash': digest, 'p_lease': lease})
        if not isinstance(result, dict) or result.get('code') not in {'acquired', 'busy', 'not_found'}:
            raise APIError(503, 'cloud_unavailable', 'Não foi possível recuperar o atendimento.')
        if result['code'] == 'not_found':
            raise APIError(404, 'session_not_found', 'Sessão inexistente ou expirada. Abra um novo atendimento.')
        if result['code'] == 'busy':
            raise APIError(409, 'session_busy', 'Aguarde a conclusão da solicitação anterior desta sessão.')
        state = result['state']
        session = Session(bytes.fromhex(digest), 0, registered=state.get('registered', False),
                          pending=state.get('pending'), registration=state.get('registration'))
        if state.get('draft'):
            session.draft = RegistrationDraft(**state['draft'])
        session.agent = RestoredAgent(self.agent_factory, state.get('agent', {}))
        context = {'id': sid, 'closed': False}
        handle = self.current.set(context)
        try:
            yield session
        finally:
            try:
                saved = self.rpc.call('agent_session_finish', {
                    'p_id': sid, 'p_lease': lease, 'p_close': context['closed'],
                    'p_state': {'registered': session.registered, 'pending': session.pending,
                                'registration': session.registration,
                                'draft': session.draft.payload() if session.draft else None,
                                'agent': session.agent.export()}})
                if saved is not True:
                    raise APIError(503, 'state_not_saved', 'Não foi possível confirmar o estado da conversa. Aguarde e repita a mesma solicitação.')
            finally:
                self.current.reset(handle)


def make_cloud_service():
    rpc = CloudRPC()
    assets = PrivateAssets(rpc)
    def factory():
        return ConversationAgent(ChatModel(LLMSettings.load()), assets.data_dir())
    return CloudSessionService(rpc, factory)

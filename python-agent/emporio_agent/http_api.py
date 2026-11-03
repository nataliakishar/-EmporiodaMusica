"""Camada HTTP local, sem estado cadastral controlado pelo cliente."""
import os

from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException

from .api_sessions import APIError, SessionService


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator('message')
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Mensagem vazia.')
        return value


class RegistrationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    confirmed: bool
    name: str | None = Field(default=None, max_length=120, repr=False)
    phone: str | None = Field(default=None, max_length=40, repr=False)
    email: str | None = Field(default=None, max_length=254, repr=False)


class RequestGuard:
    """Limita o corpo antes do JSON e evita cache de contatos, respostas e tokens."""
    def __init__(self, app, max_bytes=32768):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
            await send(message)

        chunks, length = [], 0
        while True:
            item = await receive()
            if item['type'] == 'http.disconnect':
                return
            length += len(item.get('body', b''))
            if length > self.max_bytes:
                response = JSONResponse(status_code=413, content={
                    'code': 'body_too_large', 'message': 'Solicitação excede o limite de 32 KiB.'})
                return await response(scope, receive, secure_send)
            chunks.append(item)
            if not item.get('more_body', False):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                item = chunks[index]
                index += 1
                return item
            return await receive()

        await self.app(scope, replay, secure_send)


def create_app(service=None, *, allowed_origins=None):
    service = service or SessionService()
    app = FastAPI(title='Empório da Música — API local', version='0.1.0', debug=False)
    app.state.sessions = service
    if allowed_origins is None:
        allowed_origins = os.environ.get('API_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    origins = [origin.strip() for origin in allowed_origins if origin.strip()]
    if '*' in origins:
        raise ValueError('Configure origens explícitas em API_ALLOWED_ORIGINS.')
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Authorization', 'Content-Type'],
                       expose_headers=['Retry-After'])
    app.add_middleware(RequestGuard)

    @app.exception_handler(APIError)
    async def api_error(_, error):
        retry = error.payload.get('retry_after_seconds')
        return JSONResponse(status_code=error.status, content=error.payload,
                            headers={'Retry-After': str(retry)} if retry is not None else None)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_, error):
        # O padrão do FastAPI inclui o valor rejeitado; aqui não ecoamos contatos.
        known = {'message', 'name', 'phone', 'email', 'confirmed'}
        fields = sorted({str(part) for item in error.errors() for part in item.get('loc', ()) if part in known})
        return JSONResponse(status_code=422, content={
            'code': 'invalid_request', 'message': 'Confira os campos da solicitação.', 'fields': fields})

    @app.exception_handler(HTTPException)
    async def http_error(_, error):
        return JSONResponse(status_code=error.status_code, content={
            'code': 'http_error', 'message': 'Rota ou método HTTP não disponível.'})

    def token(authorization):
        if not authorization or not authorization.startswith('Bearer '):
            return None
        return authorization[7:]

    def invoke(operation):
        try:
            return operation()
        except APIError:
            raise
        except Exception:
            raise APIError(500, 'internal_error', 'Não foi possível concluir a solicitação.') from None

    @app.get('/health')
    def health():
        return {'status': 'ok', 'session_storage': 'memory', 'private_order_authentication': False}

    @app.post('/sessions', status_code=201)
    def open_session():
        return invoke(service.create)

    @app.post('/sessions/{session_id}/messages')
    def send_message(session_id: str, body: MessageInput, authorization: str | None = Header(default=None)):
        result = invoke(lambda: service.message(session_id, token(authorization), body.message))
        return JSONResponse(status_code=202 if result['code'] == 'registration_required' else 200, content=result)

    @app.post('/sessions/{session_id}/registration')
    def confirm_registration(session_id: str, body: RegistrationInput, authorization: str | None = Header(default=None)):
        return invoke(lambda: service.register(session_id, token(authorization), **body.model_dump()))

    @app.post('/sessions/{session_id}/clear')
    def clear_context(session_id: str, authorization: str | None = Header(default=None)):
        return invoke(lambda: service.clear(session_id, token(authorization)))

    @app.delete('/sessions/{session_id}')
    def close_session(session_id: str, authorization: str | None = Header(default=None)):
        return invoke(lambda: service.close(session_id, token(authorization)))

    return app

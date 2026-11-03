"""Gravação restrita ao endpoint fixo do cadastro, com repetição idempotente."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import PROJECT_ROOT
from .registration import RegistrationDraft, RegistrationError


@dataclass(frozen=True)
class RegistrationSettings:
    url: str
    secret_key: str = field(repr=False)

    @classmethod
    def load(cls, root=PROJECT_ROOT, environ=None):
        keys={'SUPABASE_URL','SUPABASE_SECRET_KEY'}
        values={}
        for path in (root/'.env',root/'python-agent/.env'):
            if not path.exists():
                continue
            try:
                for line in path.read_text(encoding='utf-8-sig').splitlines():
                    key,sep,value=line.strip().partition('=')
                    if sep and key.strip() in keys:
                        value=value.strip()
                        if value[:1] in ('\"',"'"):
                            if len(value)<2 or value[-1]!=value[0]:
                                raise RegistrationError('Aspas inválidas na configuração do Supabase.')
                            value=value[1:-1]
                        else:
                            value=value.split(' #',1)[0].rstrip()
                        values[key.strip()]=value
            except (OSError,UnicodeError):
                raise RegistrationError('Confira a configuração Supabase no .env local.') from None
        env=os.environ if environ is None else environ
        values.update({k:env[k] for k in keys if k in env})
        url=values.get('SUPABASE_URL','').strip().rstrip('/')
        try:
            parsed=urlsplit(url)
            port=parsed.port
        except ValueError:
            raise RegistrationError('Configure SUPABASE_URL com a URL HTTPS oficial do projeto no .env local.') from None
        if (parsed.scheme!='https' or not re_host(parsed.hostname) or parsed.username or parsed.password
                or port not in (None,443) or parsed.path or parsed.query or parsed.fragment):
            raise RegistrationError('Configure SUPABASE_URL com a URL HTTPS oficial do projeto no .env local.')
        key=values.get('SUPABASE_SECRET_KEY','').strip()
        if not key.startswith('sb_secret_') or any(c.isspace() for c in key) or len(key)<25:
            raise RegistrationError('Configure SUPABASE_SECRET_KEY no .env local com uma chave de backend sb_secret_. Nunca envie a chave no chat.')
        return cls(url,key)


def re_host(host):
    import re
    return bool(host and re.fullmatch(r'[a-z0-9]{20}\.supabase\.co',host))


class NoRegistrationRedirects(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RegistrationError('O Supabase tentou redirecionar o cadastro. Confira SUPABASE_URL; nenhum redirecionamento foi seguido.')


class RegistrationStore:
    def __init__(self, settings, opener=None):
        self.settings=settings
        self.opener=opener if opener is not None else build_opener(NoRegistrationRedirects())

    def save(self,draft: RegistrationDraft):
        body=json.dumps(draft.payload(),ensure_ascii=False).encode('utf-8')
        request=Request(self.settings.url+'/rest/v1/customer_registrations?on_conflict=id&select=id',data=body,
                        headers={'apikey':self.settings.secret_key,'Content-Type':'application/json','Accept':'application/json',
                                 'Prefer':'resolution=ignore-duplicates,return=representation'},method='POST')
        for attempt in range(2):
            try:
                with self.opener.open(request,timeout=20) as response:
                    raw=response.read(4097)
                    if len(raw)>4096:
                        raise RegistrationError('O cadastro retornou uma resposta inesperada; confirme com a equipe pelo protocolo '+draft.id+'.')
                    result=json.loads(raw)
                    # [] indica repetição da mesma submissão, ignorada pelo UUID.
                    if result not in ([],[{'id':draft.id}]):
                        raise RegistrationError('O cadastro retornou um protocolo inesperado; confirme com a equipe.')
                return {'code':'registration_saved','registration_id':draft.id,
                        'message':'Cadastro recebido. Este protocolo não autentica acesso a pedidos.'}
            except HTTPError as error:
                error.close()
                if error.code in (502,503,504) and not attempt:
                    continue
                if error.code in (401,403):
                    raise RegistrationError('O Supabase recusou a chave ou a permissão de cadastro. Confira a configuração de backend.') from None
                if error.code==400:
                    raise RegistrationError('O Supabase recusou o cadastro. Confira os dados e a migração do banco.') from None
                raise RegistrationError('Não foi possível confirmar o cadastro. Confirme com a equipe pelo protocolo '+draft.id+' antes de enviar outro.') from None
            except (URLError,TimeoutError,OSError):
                if not attempt:
                    continue
                raise RegistrationError('Não foi possível confirmar o cadastro. Confirme com a equipe pelo protocolo '+draft.id+' antes de enviar outro.') from None
            except (ValueError,UnicodeError) as error:
                if isinstance(error,RegistrationError):
                    raise
                raise RegistrationError('Resposta inválida no cadastro. Confirme com a equipe pelo protocolo '+draft.id+'.') from None

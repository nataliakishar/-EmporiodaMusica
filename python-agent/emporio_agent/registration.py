"""Cadastro mínimo independente do LLM; valores pessoais não vão para a Groq."""
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from uuid import uuid4


class RegistrationError(ValueError):
    pass


def _text(value, field):
    if not isinstance(value, str) or any(unicodedata.category(c).startswith('C') for c in value):
        raise RegistrationError(f'Informe {field} válido, sem caracteres de controle.')
    return unicodedata.normalize('NFKC', value).strip()


@dataclass(frozen=True, repr=False)
class RegistrationDraft:
    id: str
    name: str
    phone: str
    email: str

    def __repr__(self):
        return f'RegistrationDraft(id={self.id!r})'

    @classmethod
    def prepare(cls, name, phone, email):
        name=' '.join(_text(name, 'um nome').split())
        if not 2 <= len(name) <= 120 or not any(c.isalpha() for c in name):
            raise RegistrationError('O nome deve ter entre 2 e 120 caracteres e conter letras.')
        raw=_text(phone, 'um telefone')
        if len(raw)>40 or not re.fullmatch(r'[+0-9 ().-]+', raw):
            raise RegistrationError('Informe um telefone brasileiro com DDD.')
        number=re.sub(r'[ ().-]', '', raw)
        if number.startswith('+55'):
            number=number[3:]
        elif number.startswith('55') and len(number) in (12,13):
            number=number[2:]
        if not re.fullmatch(r'[1-9][0-9][2-9][0-9]{7,8}', number):
            raise RegistrationError('Informe um telefone brasileiro com DDD; esta fase aceita o código +55.')
        phone='+55'+number
        email=_text(email, 'um e-mail')
        if email.count('@')!=1 or len(email)>254:
            raise RegistrationError('Informe um e-mail válido, como nome@dominio.com.')
        local,domain=email.rsplit('@',1)
        try:
            domain=domain.encode('idna').decode('ascii').lower()
        except UnicodeError:
            raise RegistrationError('Informe um domínio de e-mail válido.') from None
        local=local.lower()
        if (not 1<=len(local)<=64 or not re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]+",local)
                or local.startswith('.') or local.endswith('.') or '..' in local
                or '.' not in domain or len(domain)>253
                or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in domain.split('.'))):
            raise RegistrationError('Informe um e-mail válido, como nome@dominio.com.')
        email=local+'@'+domain
        if len(email)>254:
            raise RegistrationError('O e-mail excede o tamanho permitido.')
        return cls(str(uuid4()),name,phone,email)

    def payload(self):
        return {'id':self.id,'name':self.name,'phone':self.phone,'email':self.email}

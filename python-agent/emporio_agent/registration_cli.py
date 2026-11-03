"""Coleta explícita de dados, sem LLM, antes da gravação no Supabase."""
import json
import sys

from .registration import RegistrationDraft, RegistrationError
from .registration_store import RegistrationSettings, RegistrationStore


def run_registration(json_output=False,dry_run=False,confirmed=False):
    try:
        if json_output:
            raw=sys.stdin.read(4097)
            if len(raw)>4096:
                raise RegistrationError('O cadastro excede o tamanho permitido.')
            try:
                data=json.loads(raw)
            except ValueError:
                raise RegistrationError('Envie JSON com somente name, phone e email pela entrada padrão.') from None
            if not isinstance(data,dict) or set(data)!={'name','phone','email'}:
                raise RegistrationError('O cadastro deve conter somente name, phone e email.')
            draft=RegistrationDraft.prepare(**data)
        else:
            draft=RegistrationDraft.prepare(input('Nome: '),input('Telefone com DDD: '),input('E-mail: '))
        if dry_run:
            result={'code':'registration_valid','message':'Dados válidos. Nenhum cadastro foi gravado.'}
        else:
            if not json_output:
                print(f'Confira os dados: {draft.name} | {draft.phone} | {draft.email}')
                confirmed=input('Confirma o envio destes dados à loja? [s/N]: ').strip().casefold() in ('s','sim')
            if not confirmed:
                result={'code':'registration_cancelled','message':'Cadastro não enviado; é necessária confirmação explícita.'}
            else:
                result=RegistrationStore(RegistrationSettings.load()).save(draft)
        print(json.dumps(result,ensure_ascii=False) if json_output else result['message'])
        if not json_output and result.get('registration_id'):
            print('Protocolo: '+result['registration_id'])
        return 0
    except (EOFError,KeyboardInterrupt):
        print(json.dumps({'code':'registration_cancelled','message':'Cadastro cancelado; nenhuma gravação foi solicitada.'})
              if json_output else '\nCadastro cancelado.')
        return 0

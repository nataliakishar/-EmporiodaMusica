"""Entrada obrigatória do atendimento; contatos nunca entram no contexto do LLM."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .registration import RegistrationDraft, RegistrationError
from .registration_store import RegistrationSettings, RegistrationStore


PRIVACY_NOTICE = (
    'Para continuar o atendimento, precisamos do seu nome, telefone e e-mail para cadastro '
    'e contato sobre esta solicitação. Em atenção à transparência prevista na LGPD '
    '(Lei nº 13.709/2018), você poderá conferir os dados antes de confirmar o envio. '
    'Se preferir cancelar, este atendimento não prosseguirá. '
    'O cadastro não autoriza publicidade nem autentica acesso a pedidos privados.'
)
RETURNING_MESSAGE = 'Já encontramos um cadastro com esses contatos. Obrigado por retornar à Empório da Música!'
NEW_MESSAGE = 'Obrigado pelas informações! Seu cadastro foi realizado. Vamos continuar seu atendimento.'


class ConversationRegistrationStore(RegistrationStore):
    def resolve(self, draft: RegistrationDraft):
        payload={'p_id':draft.id,'p_name':draft.name,'p_phone':draft.phone,'p_email':draft.email}
        request=Request(self.settings.url+'/rest/v1/rpc/resolve_customer_registration',
                        data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
                        headers={'apikey':self.settings.secret_key,'Content-Type':'application/json','Accept':'application/json'},
                        method='POST')
        for attempt in range(2):
            try:
                with self.opener.open(request,timeout=20) as response:
                    raw=response.read(4097)
                    if len(raw)>4096:
                        raise RegistrationError('Não foi possível confirmar o cadastro; o atendimento não foi liberado.')
                    result=json.loads(raw)
                if not isinstance(result,list) or len(result)!=1 or not isinstance(result[0],dict):
                    raise RegistrationError('Resposta inesperada na conferência do cadastro; o atendimento não foi liberado.')
                row=result[0]
                if set(row)!={'is_existing','submission_id'} or type(row['is_existing']) is not bool:
                    raise RegistrationError('Resposta inesperada na conferência do cadastro; o atendimento não foi liberado.')
                if row['is_existing'] and row['submission_id'] is None:
                    return {'code':'registration_existing','message':RETURNING_MESSAGE}
                if row['is_existing'] is False and row['submission_id']==draft.id:
                    return {'code':'registration_saved','message':NEW_MESSAGE,'registration_id':draft.id}
                raise RegistrationError('Protocolo inesperado no cadastro; o atendimento não foi liberado.')
            except HTTPError as error:
                error.close()
                if error.code in (502,503,504) and not attempt:
                    continue
                raise RegistrationError('Não foi possível confirmar o cadastro no Supabase. O atendimento não foi liberado; tente novamente mais tarde.') from None
            except (URLError,TimeoutError,OSError):
                if not attempt:
                    continue
                raise RegistrationError('Não foi possível confirmar o cadastro. O atendimento não foi liberado; tente novamente mais tarde.') from None
            except (ValueError,UnicodeError) as error:
                if isinstance(error,RegistrationError):
                    raise
                raise RegistrationError('Resposta inválida na conferência do cadastro; o atendimento não foi liberado.') from None


def complete_conversation_registration():
    print('Empório: '+PRIVACY_NOTICE)
    while True:
        try:
            draft=RegistrationDraft.prepare(input('Nome: '),input('Telefone com DDD: '),input('E-mail: '))
        except RegistrationError as error:
            print('Empório: '+str(error))
            if input('Deseja corrigir os dados? [s/N]: ').strip().casefold() in ('s','sim'):
                continue
            return None
        print(f'Confira os dados: {draft.name} | {draft.phone} | {draft.email}')
        if input('Confirma o envio destes dados à loja? [s/N]: ').strip().casefold() not in ('s','sim'):
            return None
        result=ConversationRegistrationStore(RegistrationSettings.load()).resolve(draft)
        print('Empório: '+result['message'])
        if result.get('registration_id'):
            print('Protocolo: '+result['registration_id'])
        return result

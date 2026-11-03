"""Somente o novo fluxo de entrada; LLM e Supabase são dublês explícitos."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from emporio_agent.chat_cli import run_chat
from emporio_agent.conversation_registration import ConversationRegistrationStore, complete_conversation_registration
from emporio_agent.registration import RegistrationDraft, RegistrationError
from emporio_agent.registration_store import RegistrationSettings

DATA={'name':'Cliente Fluxo Teste','phone':'(67) 99999-1234','email':'fluxo@example.invalid'}
URL='https://abcdefghijklmnopqrst.supabase.co'
KEY='sb_secret_test_fixture_never_real_123'


class ConversationGateTransportTests(unittest.TestCase):
    def setUp(self):
        self.draft=RegistrationDraft.prepare(**DATA)
        self.opener=Mock()
        self.store=ConversationRegistrationStore(RegistrationSettings(URL,KEY),self.opener)

    def reply(self,existing=False,submission=None):
        return BytesIO(json.dumps([{'is_existing':existing,'submission_id':submission}]).encode())

    def test_new_customer_returns_new_receipt_from_fixed_rpc(self):
        self.opener.open.return_value=self.reply(submission=self.draft.id)
        result=self.store.resolve(self.draft)
        request=self.opener.open.call_args.args[0]
        self.assertEqual(result['code'],'registration_saved')
        self.assertEqual(result['registration_id'],self.draft.id)
        self.assertTrue(request.full_url.endswith('/rpc/resolve_customer_registration'))
        self.assertNotIn(self.draft.phone,request.full_url)
        self.assertEqual(json.loads(request.data)['p_email'],self.draft.email)

    def test_returning_customer_does_not_expose_stored_id_or_personal_fields(self):
        self.opener.open.return_value=self.reply(existing=True)
        result=self.store.resolve(self.draft)
        self.assertEqual(result['code'],'registration_existing')
        self.assertIn('Obrigado por retornar',result['message'])
        self.assertNotIn('registration_id',result)
        self.assertNotIn(self.draft.email,json.dumps(result))

    def test_uncertain_retry_reuses_submission_without_changing_customer_kind(self):
        self.opener.open.side_effect=[HTTPError(URL,503,'temporary',{},BytesIO(b'private')),
                                      self.reply(submission=self.draft.id)]
        self.assertEqual(self.store.resolve(self.draft)['code'],'registration_saved')
        self.assertEqual(self.opener.open.call_args_list[0].args[0].data,self.opener.open.call_args_list[1].args[0].data)

    def test_failed_lookup_never_releases_chat_or_echoes_body(self):
        self.opener.open.side_effect=HTTPError(URL,403,'forbidden',{},BytesIO(KEY.encode()))
        with self.assertRaises(RegistrationError) as error:
            self.store.resolve(self.draft)
        self.assertNotIn(KEY,str(error.exception))
        self.assertEqual(self.opener.open.call_count,1)

    def test_network_attempts_are_bounded(self):
        self.opener.open.side_effect=URLError('private '+KEY)
        with self.assertRaises(RegistrationError) as error:
            self.store.resolve(self.draft)
        self.assertEqual(self.opener.open.call_count,2)
        self.assertNotIn(KEY,str(error.exception))

    def test_invalid_or_overbroad_rpc_response_is_rejected(self):
        cases=[[],[{'is_existing':'true','submission_id':None}],
               [{'is_existing':True,'submission_id':self.draft.id}],
               [{'is_existing':False,'submission_id':'wrong'}],
               [{'is_existing':True,'submission_id':None,'email':DATA['email']}]]
        for response in cases:
            self.opener.open.return_value=BytesIO(json.dumps(response).encode())
            with self.subTest(keys=str(type(response))),self.assertRaises(RegistrationError):
                self.store.resolve(self.draft)


class ConversationGateCollectionTests(unittest.TestCase):
    def test_refusal_never_accesses_database(self):
        with patch('builtins.input',side_effect=[*DATA.values(),'n']),patch('emporio_agent.conversation_registration.ConversationRegistrationStore') as store,redirect_stdout(StringIO()):
            self.assertIsNone(complete_conversation_registration())
        store.assert_not_called()

    def test_invalid_fields_can_be_corrected_before_confirmation(self):
        values=['A',DATA['phone'],DATA['email'],'s',*DATA.values(),'s']
        with patch('builtins.input',side_effect=values),patch('emporio_agent.conversation_registration.RegistrationSettings.load'),patch('emporio_agent.conversation_registration.ConversationRegistrationStore') as store,redirect_stdout(StringIO()) as out:
            store.return_value.resolve.return_value={'code':'registration_existing','message':'Obrigado por retornar.'}
            result=complete_conversation_registration()
        self.assertEqual(result['code'],'registration_existing')
        self.assertIn('LGPD',out.getvalue())
        store.return_value.resolve.assert_called_once()


class MandatoryChatFlowTests(unittest.TestCase):
    def test_actual_collection_returns_to_question_without_contacts_in_llm_call(self):
        inputs=['Quanto custa o Takamine?',*DATA.values(),'s','/sair']
        with patch('builtins.input',side_effect=inputs),patch('emporio_agent.conversation_registration.RegistrationSettings.load'),patch('emporio_agent.conversation_registration.ConversationRegistrationStore') as store,patch('emporio_agent.chat_cli.LLMSettings.load',return_value=SimpleNamespace()),patch('emporio_agent.chat_cli.ChatModel'),patch('emporio_agent.chat_cli.ConversationAgent') as agent,redirect_stdout(StringIO()):
            store.return_value.resolve.return_value={'code':'registration_existing','message':'Obrigado por retornar.'}
            agent.return_value.ask.return_value=SimpleNamespace(text='Resposta de teste.',tools=[])
            self.assertEqual(run_chat(),0)
        agent.return_value.ask.assert_called_once_with('Quanto custa o Takamine?')
        draft=store.return_value.resolve.call_args.args[0]
        self.assertEqual(draft.email,DATA['email'])

    def run_flow(self,inputs,gate=None,message=None,json_output=False):
        output=StringIO()
        profile={'code':'registration_existing'} if gate is None else gate
        with patch('builtins.input',side_effect=inputs),patch('emporio_agent.chat_cli.complete_conversation_registration',return_value=profile) as collect,patch('emporio_agent.chat_cli.LLMSettings.load',return_value=SimpleNamespace(provider='test',model='fake')),patch('emporio_agent.chat_cli.ChatModel'),patch('emporio_agent.chat_cli.ConversationAgent') as agent,redirect_stdout(output):
            agent.return_value.ask.return_value=SimpleNamespace(text='Resposta de catálogo do dublê.',tools=[])
            code=run_chat(message,json_output)
        return code,collect,agent,output.getvalue()

    def test_first_question_waits_for_registration_and_is_asked_only_once(self):
        events=[]
        with patch('builtins.input',side_effect=['Quanto custa o Takamine?','E o estoque?','/sair']),patch('emporio_agent.chat_cli.complete_conversation_registration',side_effect=lambda:events.append('cadastro') or {'code':'registration_saved'}) as collect,patch('emporio_agent.chat_cli.LLMSettings.load',return_value=SimpleNamespace()),patch('emporio_agent.chat_cli.ChatModel'),patch('emporio_agent.chat_cli.ConversationAgent') as agent,redirect_stdout(StringIO()):
            agent.return_value.ask.side_effect=lambda question:events.append(question) or SimpleNamespace(text='Resposta de teste.',tools=[])
            self.assertEqual(run_chat(),0)
        self.assertEqual(events,['cadastro','Quanto custa o Takamine?','E o estoque?'])
        collect.assert_called_once()

    def test_refusal_stops_before_creating_llm(self):
        with patch('builtins.input',side_effect=['Quanto custa um violão?']),patch('emporio_agent.chat_cli.complete_conversation_registration',return_value=None),patch('emporio_agent.chat_cli.ConversationAgent') as agent,patch('emporio_agent.chat_cli.LLMSettings.load') as settings,redirect_stdout(StringIO()):
            self.assertEqual(run_chat(),0)
        settings.assert_not_called()
        agent.assert_not_called()

    def test_lookup_error_stops_before_llm(self):
        with patch('builtins.input',side_effect=['Pergunta']),patch('emporio_agent.chat_cli.complete_conversation_registration',side_effect=RegistrationError('Falha de teste')),patch('emporio_agent.chat_cli.ConversationAgent') as agent,redirect_stdout(StringIO()):
            self.assertEqual(run_chat(),2)
        agent.assert_not_called()

    def test_clear_context_does_not_require_contacts_again(self):
        code,collect,agent,out=self.run_flow(['Primeira pergunta','/limpar','Outra pergunta','/sair'])
        collect.assert_called_once()
        agent.return_value.reset.assert_called_once()
        self.assertEqual(agent.return_value.ask.call_args_list,[call('Primeira pergunta'),call('Outra pergunta')])

    def test_new_session_requires_profile_again(self):
        for _ in range(2):
            code,collect,agent,out=self.run_flow(['Pergunta','/sair'])
            collect.assert_called_once()

    def test_explicit_registration_before_question_uses_same_gate(self):
        code,collect,agent,out=self.run_flow(['/cadastro','Pergunta','/cadastro','/sair'])
        collect.assert_called_once()
        agent.return_value.ask.assert_called_once_with('Pergunta')

    def test_one_shot_question_does_not_bypass_registration(self):
        code,collect,agent,out=self.run_flow([],message='Quanto custa o Takamine?')
        collect.assert_called_once()
        agent.return_value.ask.assert_called_once_with('Quanto custa o Takamine?')

    def test_json_message_is_blocked_without_profile_and_no_prompt_or_llm(self):
        code,collect,agent,out=self.run_flow([],message='Pergunta',json_output=True)
        self.assertEqual(code,2)
        self.assertEqual(json.loads(out)['code'],'registration_required')
        collect.assert_not_called()
        agent.assert_not_called()

    def test_unexpected_gate_result_never_releases_chat(self):
        code,collect,agent,out=self.run_flow(['Pergunta'],gate={'code':'registration_cancelled'})
        self.assertEqual(code,2)
        agent.assert_not_called()


if __name__=='__main__':
    unittest.main()

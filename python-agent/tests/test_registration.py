"""Testes focados do novo cadastro; nenhuma chamada real a LLM ou Supabase."""
from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from emporio_agent.registration import RegistrationDraft, RegistrationError
from emporio_agent.registration_store import RegistrationSettings, RegistrationStore, NoRegistrationRedirects
from emporio_agent.cli import main
from emporio_agent.chat_cli import run_chat

URL='https://abcdefghijklmnopqrst.supabase.co'
KEY='sb_secret_test_fixture_never_real_123'
DATA={'name':'Cliente de Teste','phone':'(67) 99999-1234','email':'cadastro@example.invalid'}


class RegistrationValidationTests(unittest.TestCase):
    def test_canonical_fields_and_private_repr(self):
        draft=RegistrationDraft.prepare('  Ana  D’Ávila  ', '(67) 99999-1234', 'ANA@Exemplo.COM')
        self.assertEqual((draft.name,draft.phone,draft.email),('Ana D’Ávila','+5567999991234','ana@exemplo.com'))
        self.assertNotIn(draft.name,repr(draft))
        self.assertNotIn(draft.email,repr(draft))

    def test_invalid_fields_never_echo_personal_input(self):
        for fields in ({'name':'A'},{'name':None},{'name':'Ana\x1b[31m'}, {'phone':'+1 212 555 0100'},
                       {'phone':'(00) 1111-1111'}, {'phone':'67abc99991234'}, {'email':'pessoa-sem-arroba'},
                       {'email':'ana..teste@exemplo.com'}, {'email':'a@-dominio.com'}, {'email':'a@dominio'}, {'email':True}):
            with self.subTest(fields=list(fields)):
                with self.assertRaises(RegistrationError):
                    RegistrationDraft.prepare(**(DATA|fields))

    def test_shared_email_does_not_merge_customers(self):
        one=RegistrationDraft.prepare(**DATA)
        two=RegistrationDraft.prepare(**(DATA|{'name':'Outro Cliente'}))
        self.assertEqual(one.email,two.email)
        self.assertNotEqual(one.id,two.id)

    def test_idna_domain_and_brazilian_prefix(self):
        draft=RegistrationDraft.prepare('Cliente Teste','5567999991234','nome@exémplo.com')
        self.assertEqual(draft.phone,'+5567999991234')
        self.assertIn('xn--',draft.email)


class RegistrationConfigurationTests(unittest.TestCase):
    def test_local_configuration_and_environment_precedence(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'python-agent').mkdir()
            (root/'python-agent/.env').write_text('SUPABASE_URL='+URL+'\nSUPABASE_SECRET_KEY='+KEY+'\n',encoding='utf-8')
            settings=RegistrationSettings.load(root,{})
            self.assertEqual(settings.url,URL)
            self.assertNotIn(KEY,repr(settings))
            with self.assertRaises(RegistrationError):
                RegistrationSettings.load(root,{'SUPABASE_SECRET_KEY':'sb_publishable_not_backend'})

    def test_bad_endpoints_and_missing_keys_are_rejected(self):
        with TemporaryDirectory() as tmp:
            for url in ('http://abcdefghijklmnopqrst.supabase.co','https://foreign.example',URL+'?query=1',
                        URL+'/rest/v1','https://user:password@abcdefghijklmnopqrst.supabase.co',URL+':bad',URL+':444'):
                with self.subTest(url=url), self.assertRaises(RegistrationError):
                    RegistrationSettings.load(Path(tmp),{'SUPABASE_URL':url,'SUPABASE_SECRET_KEY':KEY})
            with self.assertRaises(RegistrationError):
                RegistrationSettings.load(Path(tmp),{'SUPABASE_URL':URL})


class RegistrationTransportTests(unittest.TestCase):
    def setUp(self):
        self.draft=RegistrationDraft.prepare(**DATA)
        self.opener=Mock()
        self.store=RegistrationStore(RegistrationSettings(URL,KEY),self.opener)

    def success(self):
        return BytesIO(json.dumps([{'id':self.draft.id}]).encode())

    def test_only_expected_fields_are_written_and_only_receipt_is_returned(self):
        self.opener.open.return_value=self.success()
        result=self.store.save(self.draft)
        request=self.opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data),self.draft.payload())
        self.assertTrue(request.full_url.endswith('/customer_registrations?on_conflict=id&select=id'))
        self.assertEqual(request.get_header('Apikey'),KEY)
        self.assertEqual(result['registration_id'],self.draft.id)
        self.assertNotIn(self.draft.email,json.dumps(result))

    def test_transient_failure_reuses_exact_submission(self):
        error=HTTPError(URL,503,'temporary',{},BytesIO(b'private server body'))
        self.opener.open.side_effect=[error,self.success()]
        self.store.save(self.draft)
        first,second=[entry.args[0] for entry in self.opener.open.call_args_list]
        self.assertEqual(first.data,second.data)
        self.assertEqual(self.opener.open.call_count,2)

    def test_duplicate_submission_returns_same_receipt(self):
        self.opener.open.return_value=BytesIO(b'[]')
        self.assertEqual(self.store.save(self.draft)['registration_id'],self.draft.id)

    def test_backend_error_does_not_expose_body_or_retry_authentication(self):
        self.opener.open.side_effect=HTTPError(URL,403,'forbidden',{},BytesIO(KEY.encode()))
        with self.assertRaises(RegistrationError) as error:
            self.store.save(self.draft)
        self.assertNotIn(KEY,str(error.exception))
        self.assertEqual(self.opener.open.call_count,1)

    def test_uncertain_network_outcome_is_bounded_and_never_claims_failure_to_write(self):
        self.opener.open.side_effect=URLError('private details '+KEY)
        with self.assertRaises(RegistrationError) as error:
            self.store.save(self.draft)
        self.assertEqual(self.opener.open.call_count,2)
        self.assertIn(self.draft.id,str(error.exception))
        self.assertNotIn(KEY,str(error.exception))
        self.assertIn('confirmar',str(error.exception))

    def test_unexpected_response_is_not_success(self):
        for response in (b'not json', b'[{"id":"different"}]', b'x'*4097):
            self.opener.open.return_value=BytesIO(response)
            with self.subTest(response_size=len(response)), self.assertRaises(RegistrationError):
                self.store.save(self.draft)

    def test_redirects_never_receive_credentials(self):
        with self.assertRaises(RegistrationError):
            NoRegistrationRedirects().redirect_request(None,None,None,None,None,None)


class RegistrationCliTests(unittest.TestCase):
    def run_json(self,args,data=DATA):
        output,error=StringIO(),StringIO()
        with patch('sys.stdin',StringIO(json.dumps(data))),redirect_stdout(output),redirect_stderr(error):
            code=main(['--json','register']+args)
        return code,output.getvalue(),error.getvalue()

    def test_dry_run_has_no_network_or_llm_configuration(self):
        with patch('emporio_agent.registration_cli.RegistrationSettings.load') as settings:
            code,out,err=self.run_json(['--dry-run'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out)['code'],'registration_valid')
        settings.assert_not_called()

    def test_no_confirmation_means_no_write(self):
        with patch('emporio_agent.registration_cli.RegistrationSettings.load') as settings:
            code,out,err=self.run_json([])
        self.assertEqual(json.loads(out)['code'],'registration_cancelled')
        settings.assert_not_called()

    def test_confirmed_submission_uses_same_service_and_hides_fields_in_receipt(self):
        with patch('emporio_agent.registration_cli.RegistrationSettings.load'),patch('emporio_agent.registration_cli.RegistrationStore') as store:
            store.return_value.save.side_effect=lambda draft:{'code':'registration_saved','registration_id':draft.id,'message':'Cadastro recebido.'}
            code,out,err=self.run_json(['--confirm'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out)['code'],'registration_saved')
        self.assertNotIn(DATA['email'],out)
        store.return_value.save.assert_called_once()

    def test_extra_fields_are_rejected_without_writing(self):
        with patch('emporio_agent.registration_cli.RegistrationStore') as store:
            code,out,err=self.run_json(['--confirm'],DATA|{'is_authenticated':True})
        self.assertEqual(code,2)
        self.assertEqual(json.loads(err)['code'],'registration_error')
        store.assert_not_called()

    def test_cancelled_mandatory_registration_stops_chat_without_llm(self):
        settings=SimpleNamespace(provider='test',model='fake')
        inputs=['/cadastro',DATA['name'],DATA['phone'],DATA['email'],'n','Quanto custa um violão?','/sair']
        with patch('emporio_agent.chat_cli.LLMSettings.load',return_value=settings),patch('emporio_agent.chat_cli.ChatModel'),patch('emporio_agent.chat_cli.ConversationAgent') as agent,patch('builtins.input',side_effect=inputs),redirect_stdout(StringIO()):
            agent.return_value.ask.return_value=SimpleNamespace(text='Consulta de catálogo.',tools=[])
            self.assertEqual(run_chat(),0)
        agent.assert_not_called()


if __name__=='__main__':
    unittest.main()

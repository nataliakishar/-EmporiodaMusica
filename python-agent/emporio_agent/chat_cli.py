"""Chat interativo em linguagem natural ou pergunta única para automação."""

from dataclasses import asdict
import json

from .agent import ConversationAgent
from .config import resolve_data_dir
from .llm import ChatModel, LLMError
from .llm_config import LLMSettings
from .registration import RegistrationError
from .conversation_registration import complete_conversation_registration


def run_chat(message: str | None = None, json_output: bool = False, show_tools: bool = False, *, registration_first: bool = False) -> int:
    if json_output and message is None:
        raise LLMError("Para JSON, use chat --message com uma pergunta única.")
    if json_output:
        print(json.dumps({'code':'registration_required',
                          'message':'Para continuar, abra o chat interativo e confirme seu cadastro. Contatos não autenticam pedidos.',
                          'required_fields':['name','phone','email']},ensure_ascii=False))
        return 2
    agent = None
    registration_complete = False

    def register():
        result=complete_conversation_registration()
        if result is None:
            print('Empório: Sem a confirmação dos dados, este atendimento não prosseguirá. Cadastro não enviado.')
            return False
        if not isinstance(result,dict) or result.get('code') not in {'registration_existing','registration_saved'}:
            raise RegistrationError('Não foi possível confirmar o cadastro; o atendimento não foi liberado.')
        return True

    def get_agent():
        nonlocal agent
        if agent is None:
            settings=LLMSettings.load()
            agent=ConversationAgent(ChatModel(settings),resolve_data_dir())
        return agent

    if message is not None:
        try:
            if not register():
                return 0
        except (EOFError,KeyboardInterrupt):
            print('\nAtendimento encerrado; a pergunta não foi enviada ao modelo.')
            return 0
        answer = get_agent().ask(message)
        print(json.dumps(asdict(answer), ensure_ascii=False, indent=2) if json_output else answer.text)
        if show_tools and not json_output:
            print("Consultas: " + ", ".join(answer.tools))
        return 0
    print("Empório da Música — Sua música começa aqui.")
    print("Converse em português. O cadastro será solicitado antes de continuar. /cadastro inicia essa etapa; /limpar limpa o contexto; /sair encerra.\n")
    if registration_first:
        try:
            if not register():
                return 0
            registration_complete=True
        except RegistrationError as exc:
            print('Empório: '+str(exc)+'\n')
            return 2
        except (EOFError,KeyboardInterrupt):
            print('\nAtendimento encerrado; nenhuma pergunta foi enviada ao modelo.')
            return 0
        print('Empório: Cadastro conferido. Como posso ajudar?\n')
    while True:
        try:
            question = input("Você: ").strip()
            if question.casefold() in {"/sair", "/exit"}:
                print("Empório: Até a próxima! Boa música para você.")
                return 0
            if question.casefold() == "/limpar":
                if agent is not None:
                    agent.reset()
                print("Empório: Conversa reiniciada. Como posso ajudar?")
                continue
            if not question:
                continue
            if not registration_complete:
                try:
                    if not register():
                        return 0
                    registration_complete=True
                except RegistrationError as exc:
                    print('Empório: '+str(exc)+'\n')
                    return 2
            if question.casefold()=='/cadastro':
                print('Empório: Seus contatos já foram conferidos nesta sessão. Como posso ajudar?\n')
                continue
            try:
                answer = get_agent().ask(question)
                print("Empório: " + answer.text + "\n")
                if show_tools:
                    print("Consultas: " + ", ".join(answer.tools) + "\n")
            except LLMError as exc:
                print("Empório: " + str(exc) + "\n")
        except (EOFError, KeyboardInterrupt):
            print("\nChat encerrado. O histórico da sessão não foi salvo.")
            return 0

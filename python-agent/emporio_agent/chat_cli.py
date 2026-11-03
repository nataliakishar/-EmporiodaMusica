"""Chat interativo em linguagem natural ou pergunta única para automação."""

from dataclasses import asdict
import json

from .agent import ConversationAgent
from .config import resolve_data_dir
from .llm import ChatModel, LLMError
from .llm_config import LLMSettings
from .registration import RegistrationError


def run_chat(message: str | None = None, json_output: bool = False, show_tools: bool = False) -> int:
    settings = LLMSettings.load()
    agent = ConversationAgent(ChatModel(settings), resolve_data_dir())
    if message is not None:
        answer = agent.ask(message)
        print(json.dumps(asdict(answer), ensure_ascii=False, indent=2) if json_output else answer.text)
        if show_tools and not json_output:
            print("Consultas: " + ", ".join(answer.tools))
        return 0
    if json_output:
        raise LLMError("Para JSON, use chat --message com uma pergunta única.")
    print("Empório da Música — Sua música começa aqui.")
    print(f"Chat com LLM: {settings.provider} / {settings.model}.")
    print("Converse em português. /cadastro cadastra seus contatos; /limpar inicia outra conversa; /sair encerra. Histórico somente nesta sessão.\n")
    while True:
        try:
            question = input("Você: ").strip()
            if question.casefold() in {"/sair", "/exit"}:
                print("Empório: Até a próxima! Boa música para você.")
                return 0
            if question.casefold() == "/limpar":
                agent.reset()
                print("Empório: Conversa reiniciada. Como posso ajudar?")
                continue
            if not question:
                continue
            if question.casefold()=='/cadastro':
                from .registration_cli import run_registration
                try:
                    run_registration()
                except RegistrationError as exc:
                    print('Empório: '+str(exc)+'\n')
                continue
            try:
                answer = agent.ask(question)
                print("Empório: " + answer.text + "\n")
                if show_tools:
                    print("Consultas: " + ", ".join(answer.tools) + "\n")
            except LLMError as exc:
                print("Empório: " + str(exc) + "\n")
        except (EOFError, KeyboardInterrupt):
            print("\nChat encerrado. O histórico da sessão não foi salvo.")
            return 0

"""Adaptadores HTTP para LLMs reais com function calling; sem respostas simuladas."""

from copy import deepcopy
from dataclasses import dataclass
import json
import socket
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .llm_config import LLMSettings


class LLMError(RuntimeError):
    pass


class ToolCallError(LLMError):
    """O provedor rejeitou a geração de ferramenta antes da execução local."""


class RateLimitError(LLMError):
    def __init__(self, retry_after=None):
        super().__init__("O provedor informou limite de uso. Aguarde e tente novamente; confira as cotas do plano gratuito na Groq.")
        self.retry_after = retry_after


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LLMError("O endpoint do LLM tentou redirecionar a requisição; confira LLM_BASE_URL.")


@dataclass(frozen=True)
class ModelReply:
    message: dict
    finish_reason: str


class ChatModel:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.opener = build_opener(NoRedirects())
        self.usage = []

    def _post(self, endpoint: str, payload: dict) -> dict:
        for attempt in range(2):
            try:
                return self._post_once(endpoint, payload)
            except RateLimitError as exc:
                # Só repete uma rejeição explícita por cota, sem alterar plano/modelo.
                if self.settings.provider != "groq" or attempt or exc.retry_after is None or not 0 <= exc.retry_after <= 60:
                    raise
                sleep(exc.retry_after + 0.1)
        raise LLMError("Não foi possível concluir a chamada ao provedor.")

    def _post_once(self, endpoint: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "emporio-musica-python-agent/0.2"}
        if self.settings.provider != "ollama":
            headers["Authorization"] = "Bearer " + self.settings.api_key
        request = Request(self.settings.base_url + endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=self.settings.timeout_seconds) as response:
                body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    raise LLMError("Resposta do LLM excedeu o limite permitido.")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise ValueError
                usage = result.get('usage', {})
                if isinstance(usage, dict):
                    counts = {key:value for key,value in usage.items() if key in {'prompt_tokens','completion_tokens','total_tokens'} and type(value) is int}
                    details = usage.get('prompt_tokens_details', {})
                    if isinstance(details, dict) and type(details.get('cached_tokens')) is int:
                        counts['cached_tokens'] = details['cached_tokens']
                    self.usage.append(counts)
                return result
        except HTTPError as exc:
            if exc.code == 400 and self.settings.provider == "groq":
                try:
                    error = json.loads(exc.read(16_001)).get("error", {})
                    if isinstance(error, dict) and error.get("code") == "tool_use_failed":
                        raise ToolCallError("A Groq não gerou uma chamada de ferramenta válida. Tente novamente.") from None
                except (ValueError, AttributeError):
                    pass
            if exc.code == 429 and self.settings.provider == "groq":
                try:
                    retry_after = float(exc.headers.get("Retry-After", ""))
                except (ValueError, TypeError, AttributeError):
                    retry_after = None
                raise RateLimitError(retry_after) from None
            messages = {
                400: "O provedor recusou os parâmetros ou a chamada de ferramenta. Confira o modelo e tente uma pergunta mais específica.",
                401: "O provedor recusou a chave. Confira a configuração local.",
                403: "O provedor negou acesso ao modelo configurado.",
                404: "Endpoint ou modelo não encontrado. Confira LLM_MODEL e LLM_BASE_URL.",
                429: "O provedor informou limite ou saldo insuficiente. Tente depois ou confira sua conta.",
            }
            raise LLMError(messages.get(exc.code, f"O provedor retornou HTTP {exc.code}. Tente novamente mais tarde.")) from None
        except (TimeoutError, socket.timeout):
            raise LLMError("O LLM excedeu o tempo de resposta. Tente novamente.") from None
        except (URLError, OSError):
            raise LLMError("Não foi possível conectar ao LLM. Confira sua conexão e o serviço configurado.") from None
        except (ValueError, UnicodeError):
            raise LLMError("O provedor retornou uma resposta JSON inválida.") from None

    def complete(self, messages: list[dict], tools: list[dict], require_tool: bool = False) -> ModelReply:
        if self.settings.provider == "ollama":
            native = deepcopy(messages)
            for message in native:
                for call in message.get("tool_calls", []):
                    call["function"]["arguments"] = json.loads(call["function"]["arguments"])
                if message["role"] == "tool":
                    message["tool_name"] = message.pop("name")
                    message.pop("tool_call_id", None)
            payload = {"model": self.settings.model, "messages": native, "tools": tools,
                       "stream": False, "think": False, "options": {"temperature": 0.1, "num_predict": 800, "num_ctx": 4096}}
            if require_tool:
                # Ollama não oferece tool_choice=required: uma decisão JSON do
                # próprio modelo torna a consulta obrigatória, inclusive em follow-ups.
                schema = {"oneOf": [
                    {"type": "object", "properties": {
                        "tool": {"const": entry["function"]["name"]},
                        "arguments": entry["function"]["parameters"]},
                     "required": ["tool", "arguments"], "additionalProperties": False}
                    for entry in tools
                ]}
                choices = [{"name": t["function"]["name"], "description": t["function"]["description"],
                            "parameters": t["function"]["parameters"]} for t in tools]
                selection_instruction = (
                    "Escolha UMA ferramenta para consultar a última pergunta, considerando o histórico. "
                    "Responda somente JSON com tool e arguments. Não responda ao cliente agora. Ferramentas: "
                    + json.dumps(choices, ensure_ascii=False))
                # Um único system no início; a pergunta real fica por último.
                # System após user confundia o modelo pequeno com exemplos do prompt.
                system_content = "\n".join(m.get("content", "") for m in native if m["role"] == "system")
                native = [{"role": "system", "content": system_content + "\n" + selection_instruction}] + [
                    m for m in native if m["role"] != "system"]
                question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
                native.append({"role": "user", "content": "PERGUNTA ATUAL A CONSULTAR (exemplos do prompt não são pedidos):\n" + question})
                payload["messages"] = native
                payload.pop("tools")
                payload["format"] = schema
                payload["options"]["temperature"] = 0
            result = self._post("/api/chat", payload)
            raw = result.get("message")
            finish = result.get("done_reason", "stop")
            if require_tool and finish != "length":
                try:
                    decision = json.loads(raw["content"])
                    if (not isinstance(decision, dict) or set(decision) != {"tool", "arguments"}
                            or decision["tool"] not in {t["function"]["name"] for t in tools}
                            or not isinstance(decision["arguments"], dict)):
                        raise ValueError
                    raw = {"role": "assistant", "content": "", "tool_calls": [{
                        "function": {"name": decision["tool"], "arguments": decision["arguments"]}}]}
                except (KeyError, TypeError, ValueError):
                    raise LLMError("O LLM não retornou uma seleção de ferramenta válida.") from None
        else:
            wire_messages = deepcopy(messages)
            for message in wire_messages:
                if message["role"] == "tool":
                    message.pop("name", None)
            payload = {"model": self.settings.model, "messages": wire_messages, "tools": tools,
                       "tool_choice": "required" if require_tool else "auto", "max_completion_tokens": 1500,
                       "stream": False}
            if self.settings.provider == "openai":
                payload["store"] = False
            if self.settings.provider == "groq":
                # Reúne as correções na instrução inicial; preserva os demais
                # papéis e a ordem de perguntas, chamadas e resultados.
                instructions = [m['content'] for m in wire_messages if m['role'] == 'system']
                if len(instructions) > 1:
                    payload['messages'] = [{'role': 'system', 'content': '\n\n'.join(instructions)}] + [m for m in wire_messages if m['role'] != 'system']
                payload.update({"temperature": 0, "parallel_tool_calls": False})
                if not require_tool:
                    # Nomes, tipos e restrições permanecem. Descrições repetidas
                    # após as evidências não são necessárias para a resposta final.
                    def compact_schema(value):
                        if isinstance(value, dict):
                            return {k:compact_schema(v) for k,v in value.items() if k != 'description'}
                        if isinstance(value, list):
                            return [compact_schema(v) for v in value]
                        return value
                    payload['tools'] = compact_schema(tools)
                if self.settings.model in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
                    payload.update({"reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 2048})
                elif self.settings.model == 'qwen/qwen3.8-27b':
                    payload.update({'reasoning_effort': 'none', 'reasoning_format': 'hidden', 'max_completion_tokens': 512})
            result = self._post("/chat/completions", payload)
            try:
                choice = result["choices"][0]
                raw, finish = choice["message"], choice["finish_reason"]
            except (KeyError, IndexError, TypeError):
                raise LLMError("Resposta do LLM sem mensagem válida.") from None
        if finish in {"length", "content_filter"}:
            raise LLMError("O LLM não concluiu uma resposta utilizável. Reformule ou tente novamente.")
        if not isinstance(raw, dict) or raw.get("role", "assistant") != "assistant":
            raise LLMError("Resposta do LLM sem mensagem de assistente válida.")
        content = raw.get("content") or ""
        if not isinstance(content, str) or len(content) > 12000:
            raise LLMError("O conteúdo retornado pelo LLM é inválido.")
        calls = raw.get("tool_calls") or []
        if not isinstance(calls, list) or len(calls) > 4:
            raise LLMError("O LLM excedeu o limite de ferramentas por rodada.")
        normalized = []
        for index, call in enumerate(calls):
            try:
                function = call["function"]
                name, arguments = function["name"], function["arguments"]
                if not isinstance(name, str):
                    raise ValueError
                if self.settings.provider == "ollama" and isinstance(arguments, dict):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                if not isinstance(arguments, str) or len(arguments) > 8000:
                    raise ValueError
                identifier = call.get("id") or f"call_{index}"
                if not isinstance(identifier, str) or len(identifier) > 200:
                    raise ValueError
                normalized.append({"id": identifier, "type": "function", "function": {"name": name, "arguments": arguments}})
            except (KeyError, TypeError, ValueError):
                raise LLMError("O LLM retornou uma chamada de ferramenta inválida.") from None
        if len({c["id"] for c in normalized}) != len(normalized):
            raise LLMError("O LLM retornou identificadores de ferramentas duplicados.")
        message = {"role": "assistant", "content": content}
        if normalized:
            message["tool_calls"] = normalized
        return ModelReply(message, str(finish))

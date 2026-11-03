"""Configuração do chat: lê apenas chaves conhecidas, sem executar o .env."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit
import os

from .config import ConfigurationError, PROJECT_ROOT

KEYS = {"LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "LLM_TIMEOUT_SECONDS"}


def read_settings_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError("Não foi possível ler .env para configurar o LLM.") from exc
    result = {}
    for line in lines:
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        key = key.strip()
        if not sep or key not in KEYS:
            continue
        value = value.strip()
        if value[:1] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigurationError(f"Aspas inválidas na configuração {key}.")
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        result[key] = value
    return result


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    base_url: str
    api_key: str = field(default="", repr=False)
    timeout_seconds: int = 90

    @classmethod
    def load(cls, root: Path = PROJECT_ROOT, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        values = read_settings_file(root / ".env")
        values.update(read_settings_file(root / "python-agent" / ".env"))
        values.update({key: env[key] for key in KEYS if key in env})
        provider = values.get("LLM_PROVIDER", "openai").strip().lower()
        if provider not in {"groq", "openai", "openai_compatible", "ollama"}:
            raise ConfigurationError("LLM_PROVIDER deve ser groq, openai, openai_compatible ou ollama.")
        model = values.get("LLM_MODEL", "").strip()
        if not model or len(model) > 150 or any(ord(c) < 32 for c in model):
            raise ConfigurationError("Configure LLM_MODEL em python-agent/.env com o modelo do seu provedor.")
        default_url = {"groq": "https://api.groq.com/openai/v1", "ollama": "http://127.0.0.1:11434"}.get(provider, "https://api.openai.com/v1")
        base_url = values.get("LLM_BASE_URL", default_url).strip().rstrip("/")
        url = urlsplit(base_url)
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ConfigurationError("LLM_BASE_URL inválida; use uma URL sem credenciais, query ou fragmento.")
        loopback = url.hostname in {"localhost", "127.0.0.1", "::1"}
        if url.scheme != "https" and not (url.scheme == "http" and loopback):
            raise ConfigurationError("LLM_BASE_URL exige HTTPS; HTTP é permitido somente em localhost.")
        if provider == "openai" and (url.scheme != "https" or url.netloc != "api.openai.com" or url.path != "/v1"):
            raise ConfigurationError("Para outro endpoint, selecione explicitamente LLM_PROVIDER=openai_compatible.")
        if provider == "groq" and (url.scheme != "https" or url.netloc != "api.groq.com" or url.path != "/openai/v1"):
            raise ConfigurationError("Com LLM_PROVIDER=groq, use LLM_BASE_URL=https://api.groq.com/openai/v1.")
        key = values.get("GROQ_API_KEY", "") if provider == "groq" else (values.get("LLM_API_KEY") or values.get("OPENAI_API_KEY", ""))
        if provider == "groq" and not key.strip():
            raise ConfigurationError("Configure GROQ_API_KEY em python-agent/.env. Crie sua chave em https://console.groq.com/keys; nunca a envie no chat.")
        if provider != "ollama" and not key:
            raise ConfigurationError("Configure OPENAI_API_KEY ou LLM_API_KEY somente no .env local; nunca no chat.")
        if "\r" in key or "\n" in key:
            raise ConfigurationError("A chave configurada contém caracteres inválidos.")
        try:
            timeout = int(values.get("LLM_TIMEOUT_SECONDS", "90"))
            if not 1 <= timeout <= 180:
                raise ValueError
        except ValueError as exc:
            raise ConfigurationError("LLM_TIMEOUT_SECONDS deve estar entre 1 e 180.") from exc
        return cls(provider, model, base_url, key, timeout)

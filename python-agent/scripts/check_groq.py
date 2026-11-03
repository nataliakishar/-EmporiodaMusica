"""Confere credencial e modelo no endpoint oficial sem imprimir chave ou payload."""

import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emporio_agent.config import ConfigurationError
from emporio_agent.llm import NoRedirects, LLMError
from emporio_agent.llm_config import LLMSettings


def main():
    try:
        settings = LLMSettings.load()
        if settings.provider != "groq":
            raise ConfigurationError("Selecione LLM_PROVIDER=groq no .env local.")
        request = Request(settings.base_url + "/models", headers={
            "Authorization": "Bearer " + settings.api_key,
            "Accept": "application/json", "User-Agent": "emporio-musica-python-agent/0.2"})
        with build_opener(NoRedirects()).open(request, timeout=20) as response:
            payload = json.loads(response.read(1_000_001))
        available = settings.model in {model["id"] for model in payload["data"]}
        result = {"connection": True, "key_accepted": True, "model": settings.model, "model_available": available}
        code = 0 if available else 1
    except HTTPError as exc:
        result, code = {"connection": True, "http_status": exc.code, "key_accepted": False}, 1
    except URLError as exc:
        reason = exc.reason
        result, code = {"connection": False, "error_class": type(reason).__name__,
                        "errno": getattr(reason, "errno", None), "winerror": getattr(reason, "winerror", None)}, 1
    except (ConfigurationError, LLMError) as exc:
        result, code = {"connection": False, "message": str(exc)}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

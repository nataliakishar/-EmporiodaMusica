"""Configuração de infraestrutura; nenhum caminho local pertence às consultas."""

import os
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = PROJECT_ROOT / "python-agent"
# Último recurso de desenvolvimento, solicitado no enunciado. Não é necessário
# quando o projeto é movido: project_root/data é procurado antes deste caminho.
DEVELOPMENT_DATA_DIR = Path(
    "D:/Edital e Cursos/UFC/CTE-IA/Desafio Técnico AI Engineer 2026 - Natália/data"
)


class ConfigurationError(ValueError):
    pass


def _env_data_dir(path: Path) -> str | None:
    """Lê somente DATA_DIR, sem executar ou exportar o conteúdo do .env."""
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError("Não foi possível ler .env; configure DATA_DIR.") from exc
    result = None
    for line in lines:
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and key.strip() == "DATA_DIR":
            value = value.strip()
            if value[:1] in {"'", '"'}:
                if len(value) < 2 or value[-1] != value[0]:
                    raise ConfigurationError("DATA_DIR em .env tem aspas inválidas.")
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].rstrip()
            result = value
    return result


def resolve_data_dir(
    project_root: Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    development_fallback: Path | None = DEVELOPMENT_DATA_DIR,
) -> Path:
    """Ambiente > .env do módulo > .env do projeto > data/ > fallback local.

    Valores relativos em .env são relativos ao próprio arquivo; DATA_DIR do
    processo é relativo à raiz do projeto. Configuração explícita inválida falha
    sem consultar silenciosamente outro conjunto de dados.
    """
    environment = os.environ if environ is None else environ
    configured = environment.get("DATA_DIR")
    base = project_root
    if configured is None:
        for env_file in (project_root / "python-agent" / ".env", project_root / ".env"):
            configured = _env_data_dir(env_file)
            if configured is not None:
                base = env_file.parent
                break
    if configured is not None:
        if not configured.strip():
            raise ConfigurationError("DATA_DIR está vazio; informe a pasta dos seis CSVs.")
        path = Path(configured).expanduser()
        path = path if path.is_absolute() else base / path
        if not path.is_dir():
            raise ConfigurationError("DATA_DIR deve apontar para uma pasta existente com os seis CSVs.")
        return path.resolve()
    for candidate in (project_root / "data", project_root.parent / "data", project_root / "python-agent" / "data"):
        if candidate.is_dir():
            return candidate.resolve()
    if development_fallback is not None and development_fallback.is_dir():
        return development_fallback.resolve()
    raise ConfigurationError("Pasta data/ não encontrada; configure DATA_DIR em .env.")

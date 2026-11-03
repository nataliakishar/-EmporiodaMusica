"""Validação opt-in com LLM REAL: cinco conversas públicas, oito perguntas.

Pode gerar cobrança no provedor; não é executada nos testes automatizados.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter, sleep
import argparse

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from emporio_agent.agent import ConversationAgent
from emporio_agent.config import ConfigurationError, resolve_data_dir
from emporio_agent.data import DataValidationError, FILENAMES
from emporio_agent.data import load_snapshot
from emporio_agent.catalog import Catalog
from emporio_agent.evaluation import evaluate_turn
from emporio_agent.llm import ChatModel, LLMError
from emporio_agent.llm_config import LLMSettings

CASES = [
    ("catalogo", ["Quais opções de violões disponíveis custando até R$ 1.000?", "Qual é o mais barato dessas opções?"]),
    ("modelo", ["Quanto custa o Takamine GD20?", "Esse modelo está disponível?"]),
    ("promocoes", ["Quais produtos estão em promoção?"]),
    ("indisponibilidade", ["O Giannini GF-3D Dreadnought Sunburst está disponível? Sugira alternativas até R$ 1.000."]),
    ("privacidade_e_escopo", ["Quero saber o status do meu pedido.", "Quem ganhou a Copa do Mundo de 2022?"]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pause-seconds", type=int, default=None, choices=range(0, 61), metavar="0..60")
    args = parser.parse_args()
    reports = MODULE_ROOT / "reports"
    reports.mkdir(exist_ok=True)
    base = {"phase": 2, "tested_at_utc": datetime.now(timezone.utc).isoformat(), "real_model": True}
    try:
        settings = LLMSettings.load()
        data_dir = resolve_data_dir()
    except ConfigurationError as exc:
        result = {**base, "status": "not_configured", "real_model": False, "message": str(exc), "conversations": []}
        (reports / "live_configuration_error.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(str(exc))
        return 2
    report_path = reports / ("groq_live_validation.json" if settings.provider == "groq" else "chat_live_validation.json")
    pause = args.pause_seconds if args.pause_seconds is not None else (60 if settings.provider == "groq" else 0)
    base["pause_between_turns_seconds"] = pause
    before = {name: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest() for name, filename in FILENAMES.items()}
    conversations = []
    status, error = "completed", None
    report_path.write_text(json.dumps({**base, "provider": settings.provider, "model": settings.model, "status": "running", "conversations": []}, indent=2) + "\n", encoding="utf-8")
    catalog = Catalog(load_snapshot(data_dir))
    acceptance_passed = True
    for name, questions in CASES:
        print("Conversa real: " + name, flush=True)
        conversation = {"name": name, "turns": []}
        conversations.append(conversation)
        def observe(tool_name, result):
            print(f"    Ferramenta: {tool_name}; resultado: {result.get('code', 'dados')}; total: {result.get('total', '-')}", flush=True)
            partial = {**base, "provider": settings.provider, "model": settings.model, "status": "running",
                       "conversations": conversations, "in_progress_trace": agent.last_trace}
            report_path.write_text(json.dumps(partial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        agent = ConversationAgent(ChatModel(settings), data_dir, on_tool=observe)
        try:
            for index, question in enumerate(questions):
                if pause:
                    print(f"  Intervalo para respeitar cotas: {pause}s", flush=True)
                    sleep(pause)
                print("  Executando pergunta de teste...", flush=True)
                started = perf_counter()
                answer = agent.ask(question)
                checks = evaluate_turn(name, index, asdict(answer), catalog)
                acceptance_passed = acceptance_passed and all(checks.values())
                conversation["turns"].append({"question": question, **asdict(answer), "trace": agent.last_trace,
                                             "checks": checks,
                                             "elapsed_seconds": round(perf_counter() - started, 2)})
                partial = {**base, "provider": settings.provider, "model": settings.model,
                           "status": "running", "conversations": conversations}
                report_path.write_text(json.dumps(partial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print("  Resposta recebida; consultas: " + ", ".join(answer.tools), flush=True)
        except (LLMError, DataValidationError) as exc:
            status, error = "incomplete", str(exc)
            break
    after = {name: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest() for name, filename in FILENAMES.items()}
    if before != after:
        status = "failed_data_integrity"
    elif status == "completed" and not acceptance_passed:
        status = "failed_acceptance"
    result = {**base, "completed_at_utc": datetime.now(timezone.utc).isoformat(), "provider": settings.provider, "model": settings.model, "status": status,
              "error": error, "original_csvs_unchanged": before == after, "conversations": conversations,
              "failure_trace": agent.last_trace if error else [],
              "acceptance_checks_passed": acceptance_passed and status == "completed",
              "csv_sha256_before": before, "csv_sha256_after": after,
              "review": "Execução real registrada. Revisar semanticamente fidelidade e escolha de ferramentas; conclusão de chamadas não equivale a aprovação automática."}
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status == "completed":
        parts = ["# Conversas executadas com LLM real\n", f"Provedor: {settings.provider}; modelo: {settings.model}.\n"]
        for conversation in conversations:
            parts.append("\n## " + conversation["name"] + "\n")
            for turn in conversation["turns"]:
                parts.append("\n**Cliente:** " + turn["question"] + "\n\n**Empório:** " + turn["text"] + "\n\nConsultas: " + ", ".join(turn["tools"]) + "\n")
        examples = MODULE_ROOT / "examples"
        examples.mkdir(exist_ok=True)
        generated = "conversas_groq_executadas.md" if settings.provider == "groq" else "conversas_llm.md"
        (examples / generated).write_text("".join(parts), encoding="utf-8")
        # O caderno principal pode conter roteiros preparados pela proprietária.
        if settings.provider == "groq" and not (examples / "conversas_groq.md").exists():
            (examples / "conversas_groq.md").write_text("".join(parts), encoding="utf-8")
    print(json.dumps({"status": status, "conversations_started": len(conversations), "turns_completed": sum(len(c["turns"]) for c in conversations), "error": error}, ensure_ascii=False, indent=2))
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

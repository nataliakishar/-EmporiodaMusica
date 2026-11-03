"""Smoke opt-in da CLI com o LLM real; não executado pelo unittest."""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter, sleep
import argparse

MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))

from emporio_agent.catalog import Catalog
from emporio_agent.config import resolve_data_dir
from emporio_agent.data import load_snapshot
from emporio_agent.llm_config import LLMSettings
from emporio_agent.models import normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pause-seconds", type=int, default=None, choices=range(0, 61), metavar="0..60")
    args = parser.parse_args()
    settings = LLMSettings.load()
    pause = args.pause_seconds if args.pause_seconds is not None else (60 if settings.provider == "groq" else 0)
    catalog = Catalog(load_snapshot(resolve_data_dir()))
    cases = [
        ("modelo", "Quanto custa o Takamine GD20?", None),
        ("guitarras", "Quais guitarras estão disponíveis?", "Guitarras"),
        ("ukuleles", "Vocês têm ukuleles?", "Ukuleles"),
        ("acessorios", "Vocês vendem palhetas, pedais ou amplificadores?", None),
        ("politicas", "Quais são os horários e as regras de troca da loja?", None),
    ]
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "real_model": True,
              "provider": settings.provider, "model": settings.model, "status": "running", "pause_between_cases_seconds": pause, "cases": []}
    path = MODULE_ROOT / "reports" / ("groq_policies_cli_live.json" if settings.provider == "groq" else "policies_chat_cli_live.json")
    for name, question, category in cases:
        if report["cases"] and pause:
            print(f"  Intervalo para respeitar cotas: {pause}s", flush=True)
            sleep(pause)
        print("CLI real: " + name, flush=True)
        started = perf_counter()
        command = [sys.executable, "-X", "utf8", str(PROJECT_ROOT / "run_agent.py"),
                   "--json", "chat", "--message", question]
        completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True,
                                   encoding="utf-8", timeout=600)
        try:
            answer = json.loads(completed.stdout or completed.stderr)
        except ValueError:
            answer = {"code": "invalid_cli_output", "message": "Resposta não JSON; verificar CLI."}
        checks = {"exit_zero": completed.returncode == 0, "has_answer": bool(answer.get("text"))}
        if category:
            expected = catalog.products(category=category)
            checks["appropriate_tool"] = "consultar_produtos" in answer.get("tools", [])
            ids = expected["source"]["row_ids"]["products"]
            actual_ids = [i for source in answer.get("sources", []) for i in source.get("row_ids", {}).get("products", [])]
            checks["correct_available_products"] = actual_ids == ids
            checks["all_page_names_in_answer"] = all(normalize(p["name"]) in normalize(answer.get("text", "")) for p in expected["items"])
            checks["snapshot_notice"] = "não são dados em tempo real" in answer.get("text", "")
            if expected["next_offset"] is not None:
                checks["pagination_notice"] = f"de {expected['total']}" in answer.get("text", "")
        elif name == "modelo":
            expected = catalog.products(query="Takamine GD20", available_only=False)["items"][0]
            checks["correct_price"] = expected["price_formatted"] in answer.get("text", "")
            checks["correct_model_source"] = any(expected["product_id"] in source.get("row_ids", {}).get("products", []) for source in answer.get("sources", []))
        else:
            checks["appropriate_tool"] = bool(set(answer.get("tools", [])) & ({"consultar_escopo_loja", "informacoes_loja", "consultar_politicas"} if name == "acessorios" else {"consultar_politicas"}))
            if name == "acessorios":
                checks["scope_denial"] = "não" in answer.get("text", "").lower()
            else:
                sections = {section for source in answer.get("sources", []) for section in source.get("sections", [])}
                checks["hours_and_exchange_retrieved"] = "2" in sections and any(section.startswith("4.") for section in sections)
                checks["pdf_cited"] = "Fonte: políticas_da_loja.pdf" in answer.get("text", "")
        report["cases"].append({"name": name, "question": question, "answer": answer,
                                "checks": checks, "elapsed_seconds": round(perf_counter() - started, 2)})
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("  " + str(checks), flush=True)
        if completed.returncode != 0:
            break
    report["status"] = "passed" if len(report["cases"]) == len(cases) and all(all(c["checks"].values()) for c in report["cases"]) else "failed"
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"], flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

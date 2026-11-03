"""Executa testes, smoke tests da CLI e registra evidências sem dados privados.

Executar na raiz: python python-agent/scripts/validate.py
"""

from datetime import datetime, timezone
import hashlib
import io
import json
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import unittest

MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))

from emporio_agent.config import resolve_data_dir
from emporio_agent.data import FILENAMES, load_snapshot


def fingerprints(data_dir):
    return {name: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest() for name, filename in FILENAMES.items()}


def main():
    report_dir = MODULE_ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    data_dir = resolve_data_dir()
    before = fingerprints(data_dir)
    snapshot = load_snapshot(data_dir)
    audit = snapshot.audit
    acoustic_ids = {c.category_id for c in snapshot.categories.values() if c.name == "Violões"}
    affordable = sorted(p.product_id for p in snapshot.products.values()
                        if p.category_id in acoustic_ids and p.available and p.price_brl <= Decimal("1000"))
    audit["baseline_verification"] = {
        "supplied_claim": "Não há violões com preço de tabela até R$ 1.000,00.",
        "local_available_acoustic_guitars_up_to_1000": len(affordable),
        "available_product_ids": affordable,
        "claim_matches_local_data": not affordable,
        "decision": "Usar os CSVs locais; não fabricar ausência de resultados para reproduzir o baseline informado.",
    }
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(MODULE_ROOT / "tests"))
    tests = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    cases = [
        ("budget", ["products", "--category", "Violões", "--max-price", "1000"]),
        ("takamine", ["products", "--query", "Takamine GD20"]),
        ("guitars", ["products", "--category", "Guitarras", "--limit", "3"]),
        ("cheapest", ["products", "--category", "Violões", "--sort", "price_asc", "--limit", "1"]),
        ("ukuleles", ["products", "--category", "Ukuleles"]),
        ("promotions", ["promotions", "--limit", "20"]),
        ("unavailable", ["product", "96"]),
        ("private", ["order-status", "1"]),
    ]
    scenarios = []
    for name, arguments in cases:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(PROJECT_ROOT / "run_agent.py"), "--json", *arguments],
            cwd=PROJECT_ROOT, env={**os.environ, "DATA_DIR": str(data_dir)},
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        output = json.loads(result.stdout) if result.returncode == 0 else None
        scenarios.append({"name": name, "command": ["python", "run_agent.py", "--json", *arguments],
                          "exit_code": result.returncode, "output": output})
    after = fingerprints(data_dir)
    successful = tests.wasSuccessful() and all(s["exit_code"] == 0 for s in scenarios) and before == after
    report = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0], "phases": [0, 1],
        "success": successful,
        "tests": {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors), "skipped": len(tests.skipped)},
        "original_csvs_unchanged": before == after,
        "csv_sha256_before": before, "csv_sha256_after": after,
        "scenarios": scenarios,
        "limitations": ["Sem LLM, RAG, autenticação ou interpretação de linguagem natural nesta fase.",
                        "Os testes de baseline usam os seis CSVs originais do desafio."],
    }
    (report_dir / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "tests.txt").write_text(log.getvalue(), encoding="utf-8")
    # Cinco demonstrações REAIS da camada determinística; não são conversas LLM.
    selected = {"budget", "takamine", "promotions", "unavailable", "private"}
    examples = ["# Exemplos executados — Fase 1\n\nSaídas reais da CLI determinística. Não representam conversas com um LLM.\n"]
    for scenario in scenarios:
        if scenario["name"] in selected:
            examples.append("\n## " + scenario["name"] + "\n\n```text\n" + subprocess.list2cmdline(scenario["command"]) + "\n```\n\n```json\n" + json.dumps(scenario["output"], ensure_ascii=False, indent=2) + "\n```\n")
    example_dir = MODULE_ROOT / "examples"
    example_dir.mkdir(exist_ok=True)
    (example_dir / "consultas_cli.md").write_text("".join(examples), encoding="utf-8")
    print(json.dumps({"success": successful, "tests": report["tests"], "cli_scenarios": len(scenarios), "original_csvs_unchanged": before == after}, ensure_ascii=False, indent=2))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())

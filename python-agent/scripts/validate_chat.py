"""Registra testes do chat sem confundir dublês HTTP com inferência real."""

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from emporio_agent.config import ConfigurationError, resolve_data_dir
from emporio_agent.data import FILENAMES
from emporio_agent.llm_config import LLMSettings


def main():
    data_dir = resolve_data_dir()
    def hashes():
        return {name: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest() for name, filename in FILENAMES.items()}
    before = hashes()
    log = io.StringIO()
    tests = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.discover(str(MODULE_ROOT / "tests")))
    after = hashes()
    try:
        LLMSettings.load()
        configured = True
    except ConfigurationError:
        configured = False
    report = {
        "phase": 2, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0], "automated_tests_passed": tests.wasSuccessful(),
        "tests": {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors), "skipped": len(tests.skipped)},
        "original_csvs_unchanged": before == after, "csv_sha256_before": before, "csv_sha256_after": after,
        "provider_configuration_present": configured, "real_llm_validation": "not_run_by_this_script",
        "scope": "Orquestração com dublês, transporte HTTP local controlado, configuração, ferramentas e regressão da Fase 1.",
        "next_validation": "Execute scripts/live_chat.py com provedor real configurado; este relatório não comprova qualidade de um modelo real.",
    }
    reports = MODULE_ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "chat_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (reports / "chat_tests.txt").write_text(log.getvalue(), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("automated_tests_passed", "tests", "original_csvs_unchanged", "provider_configuration_present", "real_llm_validation")}, ensure_ascii=False, indent=2))
    return 0 if tests.wasSuccessful() and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())

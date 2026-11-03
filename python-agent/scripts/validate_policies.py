"""Testes locais e integridade do PDF/CSVs, sem chamadas ao LLM."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emporio_agent.config import resolve_data_dir
from emporio_agent.policies import FILENAME, PolicyStore
from emporio_agent.data import FILENAMES


def main():
    data = resolve_data_dir()
    files = list(FILENAMES.values()) + [FILENAME]
    def hashes():
        return {name: hashlib.sha256((data / name).read_bytes()).hexdigest() for name in files}
    before = hashes()
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    tests = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    after = hashes()
    sections, digest = PolicyStore(data).load()
    report = {"completed_at_utc": datetime.now(timezone.utc).isoformat(), "automated_tests_passed": tests.wasSuccessful(),
              "tests": {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors), "skipped": len(tests.skipped)},
              "original_sources_unchanged": before == after, "sha256_before": before, "sha256_after": after,
              "pdf_sha256": digest, "indexed_sections": len(sections), "real_model": False}
    (ROOT / "reports/policies_tests.txt").write_text(log.getvalue(), encoding="utf-8")
    (ROOT / "reports/policies_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("automated_tests_passed", "tests", "original_sources_unchanged", "indexed_sections")}, ensure_ascii=False))
    if not tests.wasSuccessful():
        print(log.getvalue()[-7000:])
    return 0 if tests.wasSuccessful() and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())

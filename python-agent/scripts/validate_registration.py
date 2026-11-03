"""Executa somente os testes do cadastro novo, sem chamadas a serviços."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from emporio_agent.config import resolve_data_dir
from emporio_agent.data import FILENAMES
from emporio_agent.policies import FILENAME


def main():
    data=resolve_data_dir()
    names=list(FILENAMES.values())+[FILENAME]
    def hashes():
        return {name:hashlib.sha256((data/name).read_bytes()).hexdigest() for name in names}
    before=hashes()
    log=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_registration.py')
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    after=hashes()
    report={'completed_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'cadastro novo somente',
            'tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)},
            'passed':result.wasSuccessful() and before==after,'original_sources_unchanged':before==after,
            'source_sha256_before':before,'source_sha256_after':after,'remote_llm_calls':0,'remote_database_calls':0}
    (ROOT/'reports/registration_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports/registration_tests.txt').write_text(log.getvalue(),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('passed','tests','original_sources_unchanged','remote_llm_calls')},ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

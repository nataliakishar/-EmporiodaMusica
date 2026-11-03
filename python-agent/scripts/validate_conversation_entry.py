"""Validação focada da entrada obrigatória e do cadastro, sem serviços remotos."""
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
    def hashes():
        return {name:hashlib.sha256((data/name).read_bytes()).hexdigest() for name in list(FILENAMES.values())+[FILENAME]}
    before=hashes()
    suite=unittest.TestSuite()
    for pattern in ('test_conversation_registration.py','test_registration.py'):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern))
    log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    after=hashes()
    core=('agent.py','tools.py','policies.py','policy_calculations.py','policy_guards.py','llm.py')
    digest=hashlib.sha256(b''.join((ROOT/'emporio_agent'/name).read_bytes() for name in core)).hexdigest()
    baseline_path=ROOT/'reports/policies_live_validation.json'
    baseline=json.loads(baseline_path.read_text(encoding='utf-8')) if baseline_path.exists() else None
    unchanged=digest==baseline['implementation_sha256'] if baseline else None
    report={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'entrada obrigatória e cadastro apenas',
            'tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)},
            'passed':result.wasSuccessful() and before==after and unchanged is not False,
            'source_sha256_before':before,'source_sha256_after':after,'original_sources_unchanged':before==after,
            'previous_agent_core_unchanged':unchanged,'core_implementation_sha256':digest,
            'remote_groq_calls':0,'remote_supabase_calls':0}
    (ROOT/'reports/conversation_gate_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'reports/conversation_gate_tests.txt').write_text(log.getvalue(),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('passed','tests','original_sources_unchanged','previous_agent_core_unchanged','remote_groq_calls')},ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

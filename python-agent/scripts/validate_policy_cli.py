"""Verificação opt-in do PDF pela CLI real, sem alterar relatórios históricos."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from emporio_agent.config import resolve_data_dir
from emporio_agent.llm_config import LLMSettings
from emporio_agent.policies import PolicyStore
from emporio_agent.policy_evaluation import evaluate_policy


def main():
    settings=LLMSettings.load()
    digest=PolicyStore(resolve_data_dir()).load()[1]
    question='Qual é o horário de funcionamento da loja durante a semana, aos sábados e nos feriados?'
    command=[sys.executable,'-X','utf8',str(ROOT.parent/'run_agent.py'),'--json','chat','--message',question]
    result=subprocess.run(command,cwd=ROOT.parent,capture_output=True,text=True,encoding='utf-8',timeout=600)
    try:
        answer=json.loads(result.stdout or result.stderr)
    except ValueError:
        answer={'error':'Saída da CLI não contém JSON válido.'}
    checks={'exit_zero':result.returncode==0,'has_answer':bool(answer.get('text'))}
    if answer.get('text'):
        checks.update(evaluate_policy(2,answer,digest))
    after=PolicyStore(resolve_data_dir()).load()[1]
    checks['pdf_unchanged']=after==digest
    report={'completed_at_utc':datetime.now(timezone.utc).isoformat(),'provider':settings.provider,'model':settings.model,
            'real_model':True,'question':question,'answer':answer,'checks':checks,'exit_code':result.returncode,
            'status':'passed' if all(checks.values()) else 'failed','pdf_sha256':digest}
    (ROOT/'reports/policies_cli_live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'checks':checks},ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':
    raise SystemExit(main())

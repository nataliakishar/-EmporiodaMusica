"""Valida 8 perguntas originais + 20 fornecidas, com LLM real e fontes operacionais."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emporio_agent.agent import ConversationAgent
from emporio_agent.catalog import Catalog
from emporio_agent.config import resolve_data_dir
from emporio_agent.data import load_snapshot, FILENAMES, DataValidationError
from emporio_agent.evaluation import evaluate_turn
from emporio_agent.policy_evaluation import evaluate_policy
from emporio_agent.policies import PolicyStore, FILENAME
from emporio_agent.llm import ChatModel, LLMError
from emporio_agent.llm_config import LLMSettings
from live_chat import CASES


class EvaluationModel(ChatModel):
    """Registra pedidos de correção do Python sem alterar mensagens ou respostas."""
    def __init__(self, settings):
        super().__init__(settings)
        self.guard_feedback = []

    def complete(self, messages, tools, require_tool=False):
        if messages and messages[-1].get('role') == 'system':
            self.guard_feedback.append(messages[-1].get('content', ''))
        return super().complete(messages, tools, require_tool=require_tool)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pause-seconds", type=int, default=60, choices=range(61), metavar="0..60")
    parser.add_argument("--only", help="IDs separados por vírgula, por exemplo p06,p13.")
    parser.add_argument("--resume", action="store_true", help="Preserva resultados aprovados da mesma implementação/fontes.")
    args = parser.parse_args()
    settings = LLMSettings.load()
    if settings.provider != "groq":
        raise SystemExit("Esta validação requer LLM_PROVIDER=groq.")
    data = resolve_data_dir()
    source_hashes = {name: hashlib.sha256((data/name).read_bytes()).hexdigest() for name in list(FILENAMES.values()) + [FILENAME]}
    implementation = hashlib.sha256(b"".join((ROOT/'emporio_agent'/name).read_bytes() for name in ("agent.py", "tools.py", "policies.py", "policy_calculations.py", "policy_guards.py", "llm.py"))).hexdigest()
    doc_hash = PolicyStore(data).load()[1]
    catalog = Catalog(load_snapshot(data))
    base = []
    for name, questions in CASES:
        for index, question in enumerate(questions):
            base.append({"id": f"b{len(base)+1:02d}", "group": "base_"+name, "case": name, "turn": index, "question": question})
    prepared = (ROOT/'examples/conversas_groq.md').read_text(encoding='utf-8').split('## Roteiros adicionais fornecidos pela proprietária',1)[1]
    policy_cases = []
    group = None
    for line in prepared.splitlines():
        if line.startswith('### '):
            group = line[4:].strip()
        if line.startswith('**Cliente:**'):
            index = len(policy_cases)
            policy_cases.append({"id": f"p{index+1:02d}", "group": "politicas_"+group, "policy_index": index, "question": line.split('**Cliente:**',1)[1].strip()})
    assert len(base) == 8 and len(policy_cases) == 20
    cases = policy_cases + base
    selected = set(args.only.split(',')) if args.only else {c['id'] for c in cases}
    if selected - {c['id'] for c in cases}:
        raise SystemExit("ID de pergunta desconhecido.")
    path = ROOT/'reports/policies_live_validation.json'
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "provider": settings.provider, "model": settings.model,
              "pause_between_cases_seconds": args.pause_seconds,
              "real_model": True, "implementation_sha256": implementation, "sources_sha256_before": source_hashes,
              "status": "running", "cases": [], "expected_cases": 28}
    if args.resume and path.is_file():
        old = json.loads(path.read_text(encoding='utf-8'))
        if (old.get('implementation_sha256') != implementation
                or old.get('sources_sha256_before') != source_hashes or old.get('model') != settings.model or old.get('provider') != settings.provider):
            raise SystemExit("Implementação, fontes ou modelo mudaram. Execute a suíte completa sem --resume; o relatório anterior foi preservado.")
        expected = {c['id']: c for c in cases}
        retained = []
        for result in old['cases']:
            case = expected.get(result['id'])
            if case is None or result['question'] != case['question']:
                continue
            if result.get('text'):
                result['checks'] = evaluate_policy(case['policy_index'], result, doc_hash) if 'policy_index' in case else evaluate_turn(case['case'], case['turn'], result, catalog)
                result['passed'] = all(result['checks'].values())
            result.setdefault('implementation_sha256',old['implementation_sha256'])
            retained.append(result)
        if not args.only:
            selected -= {r['id'] for r in retained if r.get('passed')}
        # Perguntas de continuação precisam da primeira mensagem do mesmo grupo.
        affected_groups = {c['group'] for c in base if c['id'] in selected}
        selected.update(c['id'] for c in base if c['group'] in affected_groups)
        report['cases'] = [r for r in retained if r['id'] not in selected]
        report['resumed_from_started_at_utc'] = old['started_at_utc']
    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    save()
    agents = {}
    for case in cases:
        if case['id'] not in selected:
            continue
        if args.pause_seconds:
            print(f"Intervalo de cota: {args.pause_seconds}s", flush=True)
            sleep(args.pause_seconds)
        group = case['group']
        if group not in agents:
            agents[group] = ConversationAgent(EvaluationModel(settings), data)
        agent = agents[group]
        print('Pergunta real '+case['id']+': '+case['question'], flush=True)
        started = perf_counter()
        usage_start = len(agent.model.usage)
        feedback_start = len(agent.model.guard_feedback)
        try:
            answer = asdict(agent.ask(case['question']))
            checks = evaluate_policy(case['policy_index'], answer, doc_hash) if 'policy_index' in case else evaluate_turn(case['case'], case['turn'], answer, catalog)
            result = {**case, **answer, "checks": checks, "passed": all(checks.values()), "trace": agent.last_trace,
                      "implementation_sha256": implementation,
                      "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                      "elapsed_seconds": round(perf_counter()-started,2)}
        except (LLMError, DataValidationError) as exc:
            result = {**case, "passed": False, "error": str(exc), "trace": agent.last_trace,
                      "retry_after_seconds": getattr(exc, 'retry_after', None),
                      "elapsed_seconds": round(perf_counter()-started,2)}
        report['cases'].append(result)
        result['model_usage'] = agent.model.usage[usage_start:]
        result['guard_feedback'] = agent.model.guard_feedback[feedback_start:]
        save()
        print('  '+('APROVADO' if result['passed'] else 'REVISAR: '+str(result.get('error') or [k for k,v in result['checks'].items() if not v])), flush=True)
        if result.get('error') and 'limite de uso' in result['error']:
            break
    after = {name: hashlib.sha256((data/name).read_bytes()).hexdigest() for name in source_hashes}
    report.update({"completed_at_utc": datetime.now(timezone.utc).isoformat(), "sources_sha256_after": after,
                   "original_sources_unchanged": source_hashes == after,
                   "passed_cases": sum(r['passed'] for r in report['cases']), "executed_cases": len(report['cases'])})
    report['status'] = 'completed' if len(report['cases']) == 28 and all(r['passed'] for r in report['cases']) and source_hashes == after else 'incomplete_or_failed'
    save()
    if report['status'] == 'completed':
        lines = ['# 28 perguntas executadas com Groq e fontes operacionais\n', 'PDF e CSVs consultados em execução.\n']
        for result in sorted(report['cases'], key=lambda r: (r['id'][0] == 'p', r['id'])):
            lines += ['\n## '+result['id']+'\n', '\n**Cliente:** '+result['question']+'\n\n**Empório:** '+result['text']+'\n', '\nConsultas: '+', '.join(result['tools'])+'\n']
        (ROOT/'examples/conversas_28_executadas.md').write_text(''.join(lines), encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','passed_cases','executed_cases','original_sources_unchanged')}), flush=True)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

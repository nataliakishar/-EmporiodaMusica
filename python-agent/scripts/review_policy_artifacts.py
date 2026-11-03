"""Confere as evidências locais da rodada completa; não chama o provedor."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emporio_agent.config import resolve_data_dir


def main():
    live_path = ROOT / 'reports/policies_live_validation.json'
    tests_path = ROOT / 'reports/policies_validation.json'
    live = json.loads(live_path.read_text(encoding='utf-8'))
    tests = json.loads(tests_path.read_text(encoding='utf-8'))
    cli_path = ROOT/'reports/policies_cli_live.json'
    cli = json.loads(cli_path.read_text(encoding='utf-8')) if cli_path.exists() else {}
    expected = {f'p{i:02d}' for i in range(1, 21)} | {f'b{i:02d}' for i in range(1, 9)}
    core_files = ('agent.py','tools.py','policies.py','policy_calculations.py','policy_guards.py','llm.py')
    current_implementation = hashlib.sha256(b''.join((ROOT/'emporio_agent'/name).read_bytes() for name in core_files)).hexdigest()
    checks = {
        'completed_run': live.get('status') == 'completed',
        'unique_28_questions': len(live['cases']) == 28 and {c['id'] for c in live['cases']} == expected,
        'all_acceptance_checks_passed': all(c.get('passed') and all(c['checks'].values()) for c in live['cases']),
        'real_groq': live.get('provider') == 'groq' and live.get('real_model') is True,
        'same_implementation_per_case': all(c.get('implementation_sha256') == live['implementation_sha256'] for c in live['cases']),
        'current_implementation_matches_run': current_implementation == live['implementation_sha256'],
        'local_tests_passed': tests.get('automated_tests_passed') is True,
        'real_cli_pdf_query_passed': cli.get('status') == 'passed' and cli.get('real_model') is True and cli.get('model') == live['model'],
        'test_and_live_sources_agree': tests['sha256_before'] == live['sources_sha256_before'],
        'originals_preserved_in_runs': tests['original_sources_unchanged'] and live['original_sources_unchanged'],
    }
    current = {name: hashlib.sha256((resolve_data_dir()/name).read_bytes()).hexdigest() for name in live['sources_sha256_before']}
    checks['originals_still_identical'] = current == live['sources_sha256_before'] == live['sources_sha256_after']
    transcript = ROOT/'examples/conversas_28_executadas.md'
    checks['actual_transcript_has_28_turns'] = transcript.is_file() and transcript.read_text(encoding='utf-8').count('**Cliente:**') == 28
    artifact_names = ('reports/policies_live_validation.json', 'reports/policies_validation.json', 'reports/policies_tests.txt',
                      'reports/policies_cli_live.json', 'examples/conversas_28_executadas.md', 'examples/conversas_groq.md',
                      'examples/conversas_groq_roteiros_referencia.md', 'reports/policies_semantic_review.json')
    tokens = {}
    for case in live['cases']:
        for usage in case.get('model_usage', []):
            for key, value in usage.items():
                if type(value) is int:
                    tokens[key] = tokens.get(key, 0) + value
    report = {
        'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
        'reviewer': 'Codex; verificação de artefatos e critérios, sem alegar revisão humana',
        'provider': live['provider'], 'model': live['model'], 'checks': checks,
        'status': 'passed' if all(checks.values()) else 'needs_review',
        'tests': tests['tests'], 'passed_questions': sum(c['passed'] for c in live['cases']),
        'conservative_evidence_response_cases': [c['id'] for c in live['cases'] if c.get('text','').startswith('Essa condição específica precisa de análise da equipe.')],
        'protected_private_query_cases': [c['id'] for c in live['cases'] if 'consultar_pedido' in c.get('tools',[])],
        'successful_response_token_usage': tokens,
        'usage_limit': 'Contabiliza respostas bem-sucedidas registradas nesta rodada; não inclui tentativas anteriores nem chamadas recusadas.',
        'source_sha256': current,
        'artifact_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in artifact_names if (ROOT/name).is_file()},
        'limitations': ['A aprovação vale para as 28 perguntas registradas, sem prova de fidelidade universal.',
                        'Não executa pagamentos, compras, trocas, exclusões ou consultas de pedidos privados.',
                        'As divergências e lacunas do manual exigem confirmação da equipe.'],
    }
    (ROOT/'reports/policies_artifact_review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': checks, 'tokens': tokens}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())

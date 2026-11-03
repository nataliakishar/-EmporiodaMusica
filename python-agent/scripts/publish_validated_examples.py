"""Atualiza o caderno local apenas a partir da rodada completa aprovada."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADING = '## Roteiros adicionais fornecidos pela proprietária'


def main():
    report = json.loads((ROOT/'reports/policies_live_validation.json').read_text(encoding='utf-8'))
    if report.get('status') != 'completed' or len(report['cases']) != 28 or not all(c['passed'] for c in report['cases']):
        raise SystemExit('O caderno só pode ser atualizado após a aprovação das 28 perguntas.')
    path = ROOT/'examples/conversas_groq.md'
    original = path.read_text(encoding='utf-8')
    archive = ROOT/'examples/conversas_groq_roteiros_referencia.md'
    if not archive.exists():
        archive.write_text(original, encoding='utf-8')
    prefix = original.split(HEADING, 1)[0]
    lines = prefix.splitlines()
    for index, line in enumerate(lines):
        if line.startswith('As cinco seções iniciais contêm oito perguntas'):
            lines[index] = ('As cinco seções iniciais preservam oito perguntas históricas com o modelo 120B. '
                            'As vinte perguntas adicionais abaixo agora contêm respostas efetivamente executadas com o Qwen. '
                            'A rodada atual completa, com as 28 perguntas no mesmo modelo, está em '
                            '[conversas_28_executadas.md](conversas_28_executadas.md). '
                            'Os roteiros de referência foram preservados em '
                            '[conversas_groq_roteiros_referencia.md](conversas_groq_roteiros_referencia.md).')
    lines += [HEADING, '',
              'As vinte perguntas fornecidas foram executadas com a Groq e o PDF operacional. '
              'Os textos a seguir vêm do relatório real, sem reescrever respostas para aparentar aprovação. '
              'Fontes, ferramentas e critérios estão em '
              '[policies_live_validation.json](../reports/policies_live_validation.json).', '']
    group = None
    cases = sorted((c for c in report['cases'] if 'policy_index' in c), key=lambda c:c['policy_index'])
    assert len(cases) == 20
    for case in cases:
        title = case['group'].removeprefix('politicas_')
        if title != group:
            group = title
            lines += ['### '+title, '']
        lines += ['**Cliente:** '+case['question'], '', '**Empório:** '+case['text'], '',
                  '**Consultas executadas:** '+', '.join(case['tools']), '']
    text = '\n'.join(lines).rstrip()+'\n'
    assert text.count('**Cliente:**') == 28
    path.write_text(text, encoding='utf-8')
    print('Caderno atualizado com 20 respostas reais; referências e 8 transcrições históricas preservadas.')


if __name__ == '__main__':
    main()

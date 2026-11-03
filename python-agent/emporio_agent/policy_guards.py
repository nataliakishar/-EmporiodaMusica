"""Conferências de cobertura e lacunas após retrieval; não seleciona intenção."""
import re
from .models import normalize


class PolicyIssue(str):
    def __new__(cls, message, *, requires_tool=False, review_sections=()):
        issue = super().__new__(cls, message)
        issue.requires_tool = requires_tool
        issue.review_sections = review_sections
        return issue


def evidence_for_review(results, section_ids):
    """Saída conservadora para lacuna identificada; transcreve o PDF consultado."""
    passages = {p['section']: p for result in results for p in result.get('passages', [])}
    if not section_ids or not set(section_ids) <= passages.keys():
        return None
    chunks = ['Essa condição específica precisa de análise da equipe. O manual não esclarece a aplicação dessas regras a esse caso; não posso confirmar nem negar a devolução automaticamente. Trechos consultados:']
    for section in section_ids:
        passage = passages[section]
        chunks.append('**' + passage['title'] + '**\n\n> ' + passage['text'])
    chunks.append('Peça à equipe de atendimento a análise das condições da compra antes de prosseguir.')
    return '\n\n'.join(chunks)


def policy_response_issue(question, text, results):
    norm = normalize(text)
    question_norm = normalize(question)
    passages = {p['section']: p for result in results for p in result.get('passages', [])}
    custom_return = (any(term in question_norm for term in ('personaliz', 'sob encomenda'))
                     and any(term in question_norm for term in ('devolv', 'devoluc', 'arrepend', 'mudei de ideia')))
    if custom_return:
        if not {'4.1', '4.4'} <= passages.keys():
            return PolicyIssue('A pergunta trata de devolução de item personalizado. A fonte consultada ainda não fundamenta essa resposta. Consulte consultar_politicas com topico devolucoes para obter as seções 4.1 e 4.4 antes de responder; não invente proibição nem motivos de revenda.', requires_tool=True)
        if not (any(term in norm for term in ('online', 'internet', 'distancia'))
                and any(term in norm for term in ('analis', 'confirm', 'equipe', 'gerencia'))
                and any(term in norm for term in ('nao detalh', 'nao esclarec', 'nao especific', 'nao resolve', 'nao defin', 'nao estabelece'))):
            return PolicyIssue('A seção 4.4 restringe TROCAS de personalizados. Não proíba toda devolução: diferencie a devolução online da seção 4.1, diga que o manual não esclarece esse caso específico e encaminhe para análise da equipe. Não invente motivos como revenda ou falta de reposição.', review_sections=('4.1','4.4'))
    if '4.2' in passages and '8.1' in passages and 'defeito' in question_norm and 'dias' in question_norm:
        procedure = re.search(r'(\d+)\s*(?:\([^)]*\)\s*)?dias', passages['4.2']['text'], re.IGNORECASE)
        if procedure and (procedure.group(1) not in norm or 'fabricante' not in norm):
            return 'Diferencie a garantia legal da seção 8.1 e o procedimento de troca da seção 4.2, sem extinguir a garantia legal. Explique também o prazo e o encaminhamento ao fabricante exatamente como aparecem na seção 4.2: ' + passages['4.2']['text']
    for result in results:
        primary = result.get('contacts', {}).get('whatsapp_primary')
        if primary:
            expected = re.sub(r'\D', '', primary)
            for match in re.finditer(r'whatsapp.{0,45}?(\(?\d{2}\)?[\s\u00a0\u202f-]*\d{4,5}[\s\u00a0\u202f\u2010\u2011-]*\d{4})', text, re.IGNORECASE):
                if re.sub(r'\D', '', match.group(1)) != expected and not any(t in norm for t in ('diverg', 'conflit', 'grafia')):
                    return 'Não identifique o telefone empresarial divergente como WhatsApp principal. A seção 7 identifica ' + primary + ' como canal principal; use esse contato ou sinalize a divergência.'
        if any('grafias diferentes' in n for n in result.get('notes', [])) and '@' in text:
            if not any(t in norm for t in ('diverg', 'grafia', 'confirm', 'conflit')):
                return 'O PDF contém grafias divergentes de e-mail. Não apresente uma como contato confirmado sem explicar a divergência; recomende confirmar com a equipe ou use o WhatsApp principal.'
        if result.get('topic') == 'horarios' and any(t in normalize(question) for t in ('domingo','feriado')):
            if not any(t in norm for t in ('feriado','proximo dia util','proximo dia de expediente')):
                return 'Explique quando o atendimento humano retorna: próximo dia de expediente conforme o manual; a segunda-feira só é válida se não for feriado. Não prometa atendimento em feriados.'
        operation = result.get('operation')
        fields = {
            'calcular_desconto': ('original_price_formatted','final_price_formatted'),
            'calcular_pagamento_misto': ('pix_formatted','credit_formatted','total_formatted'),
            'calcular_frete_local': ('shipping_formatted','total_formatted'),
            'calcular_parcelamento': ('total_formatted',),
        }.get(operation, ())
        required = [result[key] for key in fields if key in result]
        if operation == 'calcular_parcelamento' and result.get('installment_values_formatted'):
            required.append(result['installment_values_formatted'][0])
        if any(value not in text for value in required):
            return 'Apresente os valores monetários calculados, não apenas percentuais ou uma resposta sim/não: ' + ', '.join(dict.fromkeys(required)) + '. Use somente os cálculos retornados e respeite a elegibilidade indicada.'
        if result.get('operation') == 'calcular_pagamento_misto':
            clarified = any(term in norm for term in ('confirm', 'nao define', 'nao especifica', 'nao detalha', 'nao ha regra'))
            invented = re.search(r'(?:so|apenas|somente) se aplica.{0,40}(?:total|integral)', norm)
            if not clarified or invented:
                return 'O manual não define desconto PIX na parcela de pagamento misto. Não invente proibição ou autorização desse desconto. Apresente a divisão calculada e diga que o desconto parcial exige confirmação da equipe.'
        for passage in result.get('passages', []):
            if passage['section'] == '3.1' and 'sem valor minimo' in norm:
                if not any(term in norm for term in ('exce', 'ressalva', 'confirm')):
                    return 'A regra até três parcelas contém uma exceção no PDF. Não afirme ausência irrestrita de valor mínimo. Explique a ressalva do manual ou retire esse detalhe não solicitado.'
    local_question = any(term in question_norm for term in ('campo grande', 'regiao metropolitana'))
    if local_question and '5.1' in passages and re.search(r'R\$\s*\d', question) and 'frete' in question_norm:
        if not any(r.get('operation') == 'calcular_frete_local' for r in results):
            return PolicyIssue('A pergunta informa um valor de compra e pede frete local. Use calcular_frete_local com o valor informado antes de responder e apresente o frete, o total e o prazo retornados. Não substitua o valor informado por um produto do catálogo.', requires_tool=True)
    relevant = any(r.get('topic') in {'pagamentos','promocoes'} for r in results)
    numeric_example = re.search(r'R\$\s*\d', question) and re.search(r'\d+(?:[.,]\d+)?\s*%', question)
    calculated = any(r.get('operation') == 'calcular_desconto' for r in results)
    if relevant and numeric_example and not calculated:
        return PolicyIssue('A pergunta inclui valor e percentuais de um exemplo. Consulte calcular_desconto com os valores fornecidos e apresente o preço final calculado, além da regra de não cumulatividade. Não faça a conta mentalmente.', requires_tool=True)
    return None

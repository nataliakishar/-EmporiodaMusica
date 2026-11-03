"""Aceitação das vinte perguntas fornecidas; não participa do atendimento."""

import re
from .models import normalize


def evaluate_policy(index, answer, document_sha256):
    text = answer["text"]
    body = text.split("\n\nFonte:")[0]
    norm = normalize(body)
    tools = set(answer.get("tools", []))
    documents = [s for s in answer.get("sources", []) if s.get("document_sha256") == document_sha256]
    checks = {"pdf_consulted": bool(documents), "pdf_pages_present": bool(documents) and all(s.get("pages") for s in documents),
              "source_cited_in_reply": "Fonte: políticas_da_loja.pdf" in text,
              "no_pending_implementation_reply": "ainda não está disponível nesta fase" not in body,
              "no_unverified_shipping_promise": not re.search(r"pront[oa]s? para envio|envio imediato|entrega imediata", norm)}
    def contains(*terms):
        return all(normalize(term) in norm for term in terms)
    def matches(pattern):
        return bool(re.search(pattern, body, re.IGNORECASE | re.DOTALL))
    if index == 0:
        checks.update({"founded_2008": "2008" in norm, "address": contains("14 de Maio", "3200", "Campo Grande"),
                       "instrument_scope": contains("viol", "guitarr")})
    elif index == 1:
        checks["accessories_not_sold"] = contains("nao", "instrument") and any(t in norm for t in ("acessor", "palheta", "pedal", "amplificador"))
    elif index == 2:
        checks.update({"weekday_hours": matches(r"(?:09|9)(?::00|h)?.{0,40}18"), "saturday_hours": matches(r"s[áa]bado.{0,90}(?:09|9)(?::00|h)?.{0,30}13"),
                       "sunday_and_holidays": contains("domingo", "feriado") and any(t in norm for t in ("fechad", "nao ha", "nao funcion"))})
    elif index == 3:
        checks.update({"monday_return": contains("segunda") and matches(r"(?:09|9)(?::00|h)"),
                       "holiday_condition": "feriado" in norm or "proximo dia util" in norm, "automatic_or_human_distinction": any(t in norm for t in ("automatic", "humano", "expediente", "atendimento presencial"))})
    elif index == 4:
        checks.update({"four_payment_methods": contains("pix", "debito", "credito", "boleto"),
                       "pix_five_percent": matches(r"5\s*%"), "credit_twelve": "12" in norm,
                       "pix_not_cumulative": contains("nao", "cumul"), "boleto_compensation": matches(r"boleto.{0,130}(?:3|três|tres).{0,25}(?:dias|úteis|uteis)")})
    elif index == 5:
        checks.update({"installment_calculator_used": "calcular_parcelamento" in tools,
                       "correct_total_and_installment": "R$ 1.200,00" in body and "R$ 100,00" in body and "12" in body,
                       "no_interest": contains("sem juros")})
    elif index == 6:
        checks.update({"mixed_calculator_used": "calcular_pagamento_misto" in tools,
                       "correct_split": all(v in body for v in ("R$ 2.500,00", "R$ 1.000,00", "R$ 1.500,00")),
                       "partial_pix_discount_not_assumed": "desconto" in norm and any(t in norm for t in ("confirm", "nao defin", "nao espec", "nao detalh", "nao aplicar", "nao ha regra"))})
    elif index == 7:
        checks.update({"discount_calculator_used": "calcular_desconto" in tools,
                       "correct_promo_price": "R$ 640,00" in body and matches(r"20\s*%"),
                       "no_unverified_best_price_claim": 'melhor preco disponivel' not in norm,
                       "no_additional_pix": "pix" in norm and ("nao" in norm or "sem desconto adicional" in norm)})
    elif index == 8:
        checks.update({"seven_days_from_receipt": matches(r"7.{0,90}receb"), "refund_same_payment": contains("reembolso", "pagamento"),
                       "store_pays_return_shipping": contains("frete", "loja"), "ten_business_days": matches(r"10.{0,20}(?:dias|úteis|uteis)")})
    elif index == 9:
        checks.update({"seven_day_preference_window": "7" in body and any(t in norm for t in ("troca", "preferencia")),
                       "packaging_condition": contains("embalagem"), "stock_condition": "disponib" in norm or "estoque" in norm})
    elif index == 10:
        checks.update({"ninety_day_warranty": "90" in body, "thirty_day_procedure_not_confused": "30" in body and "fabricante" in norm})
    elif index == 11:
        checks.update({"customization_rule": "personaliz" in norm or "regulagem" in norm,
                       "online_return_not_automatically_denied": any(t in norm for t in ("online", "internet", "distancia")) and any(t in norm for t in ("analis", "confirm", "equipe", "gerencia", "nao detalh", "nao esclarec"))})
    elif index == 12:
        checks.update({"shipping_calculator_used": "calcular_frete_local" in tools, "correct_shipping_and_total": "R$ 35,00" in body and "R$ 485,00" in body,
                       "local_delivery_estimate": matches(r"1.{0,15}3.{0,20}(?:dias|úteis|uteis)")})
    elif index == 13:
        checks.update({"carriers": contains("pac", "sedex", "jadlog"),
                       "delivery_ranges": matches(r"pac.{0,110}5.{0,15}12") and matches(r"sedex.{0,110}2.{0,15}5") and matches(r"jadlog.{0,110}3.{0,15}8"),
                       "cep_based_quote": "cep" in norm, "insurance": "seguro" in norm})
    elif index == 14:
        checks.update({"tracking_notification": contains("email", "whatsapp") or ("e mail" in norm and "whatsapp" in norm),
                       "damage_refusal": "recus" in norm and "receb" in norm, "contact_store": "contato" in norm or "equipe" in norm,
                       "insurance_coverage_not_guaranteed": not re.search(r'garant\w*.{0,70}(?:cobertura|seguro)', norm) or any(term in norm for term in ('nao garante','nao garantem','nao posso garantir')),
                       "no_private_order_access": "consultar_pedido" not in tools})
    elif index == 15:
        checks.update({"annual_campaigns": contains("fevereiro", "agosto", "novembro", "black friday"),
                       "black_friday_range": matches(r"15\s*%.{0,30}30\s*%"), "does_not_confirm_active_offers": any(t in norm for t in ("vigente", "consult", "disponib", "campanha", "calendario"))})
    elif index == 16:
        checks["expired_price_not_guaranteed"] = any(t in norm for t in ("nao", "somente", "apenas")) and any(t in norm for t in ("vigente", "encerr", "termin", "expir", "anterior", "campanha"))
    elif index == 17:
        checks.update({"ninety_days": "90" in body, "manufacturer_varies": "fabricante" in norm and "6" in body and "2" in body,
                       "exclusions": contains("desgaste", "mau uso") and ("modific" in norm or "reparo" in norm)})
    elif index == 18:
        checks.update({"consent_for_marketing": "consent" in norm, "no_marketing_sharing": contains("nao", "terceiros") and any(t in norm for t in ("marketing", "publicidade", "promoco")),
                       "order_purposes": "pedido" in norm or "entrega" in norm})
    elif index == 19:
        checks.update({"deletion_request_channel": "whatsapp" in norm and "3321" in body and "4500" in body,
                       "deletion_not_executed": not re.search(r"(?:exclui|removi|removemos|apagamos) (?:seus|os seus) dados|dados (?:foram|ja estao) (?:removidos|excluidos)", norm)})
    else:
        raise ValueError("Índice de pergunta de políticas desconhecido.")
    return checks

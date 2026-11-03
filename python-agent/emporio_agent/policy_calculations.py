"""Simulações Decimal com limites extraídos do PDF; não cria compras ou pagamentos."""

from decimal import Decimal
import re

from .models import QueryError, brl, money, parse_price
from .policies import PolicyStore, PolicyError


def _match(pattern, text):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise PolicyError("A regra numérica do manual não pôde ser interpretada com segurança. Confirme a condição com a equipe.")
    return match


def simulate(store: PolicyStore, kind: str, args: dict):
    amount = parse_price(args["valor_brl"])
    if amount <= 0:
        raise QueryError("O valor da simulação deve ser positivo.")
    sections = ("3", "3.1", "6.2") if kind != "calcular_frete_local" else ("5.1",)
    result = store.retrieve(sections)
    texts = {p["section"]: p["text"] for p in result["passages"]}
    result.update({"code": "policy_simulation", "simulation": True, "operation": kind,
                   "original_price_formatted": brl(amount),
                   "notice": "Simulação pelos valores informados e regras do manual; não confirma oferta, compra, reserva ou endereço atendido."})
    if kind == "calcular_parcelamento":
        count = args["parcelas"]
        rules = texts["3.1"]
        ranges = [(int(a), int(b), parse_price(v.rstrip(".,"))) for a, b, v in re.findall(
            r"Parcelamento de (\d+)x a (\d+)x: sem juros, parcela mínima de R\$\s*([\d.,]+)", rules)]
        small = _match(r"Parcelamento em até (\d+)x:.*?exceto abaixo de R\$\s*([\d.,]+)", rules)
        if not ranges:
            raise PolicyError("As faixas de parcelamento não foram identificadas no manual.")
        maximum = max(b for a, b, v in ranges)
        if count < 1 or count > maximum:
            result.update({"eligible": False, "message": f"O manual permite até {maximum} parcelas."})
            return result
        cents = int(amount * 100)
        base, remainder = divmod(cents, count)
        payments = [Decimal(base + (1 if i < remainder else 0)) / 100 for i in range(count)]
        if count <= int(small.group(1)):
            minimum = parse_price(small.group(2).rstrip(".,"))
            if min(payments) < minimum:
                result.update({"eligible": None, "message": "A exceção para parcelas abaixo do valor indicado no manual requer confirmação da equipe.", "minimum_reference_formatted": brl(minimum)})
                return result
        else:
            candidates = [v for a, b, v in ranges if a <= count <= b]
            if len(candidates) != 1:
                raise PolicyError("Faixa de parcelamento não identificada no manual.")
            minimum = candidates[0]
        result.update({"eligible": min(payments) >= minimum, "installments": count,
                       "installment_values_formatted": [brl(p) for p in payments],
                       "minimum_installment_formatted": brl(minimum), "interest_percent": "0",
                       "total_formatted": brl(sum(payments))})
    elif kind == "calcular_pagamento_misto":
        threshold = parse_price(_match(r"compras acima de R\$\s*([\d.,]+)", texts["3.1"]).group(1).rstrip(".,"))
        pix = parse_price(args["valor_pix_brl"])
        if not 0 < pix < amount:
            raise QueryError("A parte PIX deve ser positiva e menor que o total.")
        result.update({"eligible": amount > threshold, "threshold_formatted": brl(threshold),
                       "pix_formatted": brl(pix), "credit_formatted": brl(amount - pix), "total_formatted": brl(amount),
                       "message": "O manual não define desconto PIX na parcela de um pagamento misto; não aplicar automaticamente. Confirme essa condição com a equipe."})
    elif kind == "calcular_desconto":
        percent = parse_price(args.get("desconto_percentual", "0"))
        if percent > 100:
            raise QueryError("O percentual deve estar entre 0 e 100.")
        pix_percent = Decimal(_match(r"PIX.*?(\d+(?:[.,]\d+)?)% de desconto", texts["3"]).group(1).replace(",", "."))
        applied = percent if percent > 0 else (pix_percent if args.get("usar_pix", False) else Decimal("0"))
        discount = amount - money(amount * (100 - applied) / 100)
        result.update({"discount_percent": str(applied), "discount_formatted": brl(discount),
                       "final_price_formatted": brl(amount - discount), "additional_pix_discount": False,
                       "message": "Promoções e PIX não acumulam. Se houver promoção informada, aplicar apenas o percentual promocional; a simulação não comprova promoção ativa no CSV."})
    elif kind == "calcular_frete_local":
        text = texts["5.1"]
        threshold = parse_price(_match(r"Frete grátis para pedidos acima de R\$\s*([\d.,]+)", text).group(1).rstrip(".,"))
        fee = parse_price(_match(r"taxa fixa de R\$\s*([\d.,]+)", text).group(1).rstrip(".,"))
        result["threshold_formatted"] = brl(threshold)
        if amount == threshold:
            result.update({"eligible": None, "message": "O manual distingue acima e abaixo do limiar, mas não esclarece o valor exatamente igual. Confirme o frete com a equipe."})
            return result
        shipping = Decimal("0") if amount > threshold else fee
        result.update({"shipping_formatted": brl(shipping), "total_formatted": brl(amount + shipping),
                       "message": "Condição apenas para endereço dentro da região metropolitana atendida; o prazo é a estimativa do manual, não uma cotação em tempo real."})
    else:
        raise QueryError("Simulação desconhecida.")
    return result

"""Restrições numéricas explícitas; não classifica intenção nem escolhe ferramentas."""

from decimal import Decimal
import re

from .models import CENT, QueryError, parse_price


def explicit_price_ceiling(question: str) -> Decimal | None:
    match = re.search(r"\b(at[eé]|no m[aá]ximo|menos de)\s*(?:R\$\s*(\d[\d.,]*)|(\d[\d.,]*)\s*reais\b)", question, re.IGNORECASE)
    if not match:
        return None
    raw = (match.group(2) or match.group(3)).rstrip(".,")
    if "," not in raw and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        ceiling = parse_price(raw)
        return max(Decimal("0.00"), ceiling - CENT) if match.group(1).casefold() == "menos de" else ceiling
    except QueryError:
        return None

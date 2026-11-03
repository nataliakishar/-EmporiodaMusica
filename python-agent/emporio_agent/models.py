"""Tipos públicos. Dados de clientes e pedidos não integram o catálogo."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import re
import unicodedata
from typing import Mapping

CENT = Decimal("0.01")


class QueryError(ValueError):
    pass


def normalize(text: str) -> str:
    unaccented = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", unaccented).split())


def money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def brl(amount: Decimal) -> str:
    formatted = f"{money(amount):,.2f}"
    return "R$ " + formatted.translate(str.maketrans({",": ".", ".": ","}))


def parse_price(value: str) -> Decimal:
    """Aceita 1000, 1000.50, 1000,50 ou R$ 1.000,50; rejeita negativos/NaN."""
    raw = value.strip().removeprefix("R$").strip()
    if "," in raw:
        if not re.fullmatch(r"(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,2}", raw):
            raise QueryError("Preço inválido; use 1000,50 ou 1000.50.")
        raw = raw.replace(".", "").replace(",", ".")
    elif not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        raise QueryError("Preço inválido; use 1000,50 ou 1000.50.")
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or amount < 0 or amount > Decimal("1000000000"):
            raise InvalidOperation
        return money(amount)
    except InvalidOperation as exc:
        raise QueryError("Preço fora do intervalo permitido.") from exc


@dataclass(frozen=True)
class Category:
    category_id: int
    name: str
    description: str


@dataclass(frozen=True)
class Product:
    product_id: int
    price_brl: Decimal
    name: str
    category_id: int
    description: str
    stock_quantity: int
    status: str
    specs: Mapping
    created_at: date

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: Decimal
    description: str
    is_active: bool


@dataclass(frozen=True)
class Snapshot:
    categories: Mapping[int, Category]
    products: Mapping[int, Product]
    promotions: Mapping[int, Promotion]
    audit: dict
    loaded_at_utc: str
    snapshot_sha256: str

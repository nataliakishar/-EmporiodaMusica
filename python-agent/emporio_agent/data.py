"""Leitura estrita e auditoria dos seis CSVs, sem alterar seus bytes."""

from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
from types import MappingProxyType

from .models import Category, Product, Promotion, Snapshot, money

SCHEMAS = {
    "categories": ("category_id", "name", "description"),
    "customers": ("customer_id", "name", "phone", "email", "city"),
    "products": ("product_id", "price_brl", "name", "category_id", "description", "stock_quantity", "status", "specs", "created_at"),
    "orders": ("order_id", "customer_id", "order_date", "status", "total_brl", "payment_method", "tracking_code", "estimated_delivery", "notes"),
    "order_items": ("order_id", "quantity", "product_id"),
    "promotions": ("promotion_id", "product_id", "discount_percent", "description", "is_active"),
}
FILENAMES = {name: f"desafio_tecnico_ai_eng - {name}.csv" for name in SCHEMAS}
OPTIONAL = {("orders", field) for field in ("tracking_code", "estimated_delivery", "notes")}
PRODUCT_STATUSES = {"active", "discontinued", "coming_soon"}
ORDER_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}


class DataValidationError(ValueError):
    """Erro sanitizado: informa localização do erro, nunca o valor de cliente."""


def _fail(table: str, row: int, field: str, rule: str):
    raise DataValidationError(f"{FILENAMES[table]}: linha {row}, campo {field}: {rule}.")


def _integer(value: str, table: str, row: int, field: str, minimum: int = 1) -> int:
    if not re.fullmatch(r"\d+", value):
        _fail(table, row, field, "inteiro esperado")
    result = int(value)
    if result < minimum:
        _fail(table, row, field, f"mínimo permitido {minimum}")
    return result


def _decimal(value: str, table: str, row: int, field: str, maximum: Decimal | None = None) -> Decimal:
    try:
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
            raise InvalidOperation
        result = Decimal(value)
        if not result.is_finite() or result < 0 or (maximum is not None and result > maximum):
            raise InvalidOperation
        return money(result)
    except InvalidOperation:
        _fail(table, row, field, "decimal não negativo com até duas casas esperado")


def _date(value: str, table: str, row: int, field: str) -> date | None:
    if not value and (table, field) in OPTIONAL:
        return None
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        _fail(table, row, field, "data ISO YYYY-MM-DD esperada")


def _read_csv(folder: Path, table: str) -> tuple[list[dict], dict]:
    filename = FILENAMES[table]
    try:
        content = (folder / filename).read_bytes()
    except OSError as exc:
        raise DataValidationError(f"Não foi possível ler {filename}; confira DATA_DIR em .env.") from exc
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), delimiter=",", strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or any(not x for x in headers):
            raise DataValidationError(f"{filename}: cabeçalhos vazios ou duplicados.")
        missing = set(SCHEMAS[table]) - set(headers)
        if missing:
            raise DataValidationError(f"{filename}: colunas obrigatórias ausentes: {', '.join(sorted(missing))}.")
        rows = []
        blanks = Counter()
        for row_number, raw in enumerate(reader, start=2):
            if None in raw or any(v is None for v in raw.values()):
                _fail(table, row_number, "estrutura", "quantidade de campos diferente do cabeçalho")
            row = {k: v.strip() for k, v in raw.items() if k in SCHEMAS[table]}
            for field, value in row.items():
                if not value:
                    blanks[field] += 1
                    if (table, field) not in OPTIONAL:
                        _fail(table, row_number, field, "valor obrigatório ausente")
            rows.append(row)
        if not rows:
            raise DataValidationError(f"{filename}: tabela vazia.")
    except (UnicodeError, csv.Error) as exc:
        raise DataValidationError(f"{filename}: CSV inválido; use vírgula e UTF-8. Confira DATA_DIR.") from exc
    return rows, {
        "filename": filename, "rows": len(rows), "columns": headers,
        "extra_columns_ignored": sorted(set(headers) - set(SCHEMAS[table])),
        "blank_optional_fields": dict(blanks), "sha256": hashlib.sha256(content).hexdigest(),
    }


def load_snapshot(folder: Path) -> Snapshot:
    tables, reports = {}, {}
    for table in SCHEMAS:
        tables[table], reports[table] = _read_csv(folder, table)

    identifiers = {}
    for table, rows in tables.items():
        seen = set()
        for index, row in enumerate(rows, start=2):
            if table == "order_items":
                fields = ("order_id", "product_id")
            else:
                fields = ({"categories": "category_id", "customers": "customer_id", "products": "product_id", "orders": "order_id", "promotions": "promotion_id"}[table],)
            key = tuple(_integer(row[field], table, index, field) for field in fields)
            if key in seen:
                _fail(table, index, "+".join(fields), "chave duplicada")
            seen.add(key)
        identifiers[table] = {key[0] for key in seen}
        reports[table]["unique_keys"] = len(seen)

    relationships = []
    for child, field, parent in (
        ("products", "category_id", "categories"),
        ("orders", "customer_id", "customers"),
        ("order_items", "order_id", "orders"),
        ("order_items", "product_id", "products"),
        ("promotions", "product_id", "products"),
    ):
        for index, row in enumerate(tables[child], start=2):
            identifier = _integer(row[field], child, index, field)
            if identifier not in identifiers[parent]:
                _fail(child, index, field, f"referência inexistente em {parent}")
        relationships.append({"from": f"{child}.{field}", "to": parent, "checked_rows": len(tables[child]), "orphans": 0})

    categories = {
        int(r["category_id"]): Category(int(r["category_id"]), r["name"], r["description"])
        for r in tables["categories"]
    }
    products = {}
    for index, row in enumerate(tables["products"], start=2):
        if row["status"] not in PRODUCT_STATUSES:
            _fail("products", index, "status", "status não reconhecido")
        try:
            specs = json.loads(row["specs"], parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(specs, dict):
                raise ValueError
        except (ValueError, TypeError):
            _fail("products", index, "specs", "objeto JSON válido esperado")
        product = Product(
            int(row["product_id"]), _decimal(row["price_brl"], "products", index, "price_brl"),
            row["name"], int(row["category_id"]), row["description"],
            _integer(row["stock_quantity"], "products", index, "stock_quantity", 0),
            row["status"], MappingProxyType(specs), _date(row["created_at"], "products", index, "created_at"),
        )
        products[product.product_id] = product

    email_groups = defaultdict(list)
    for row in tables["customers"]:
        email_groups[row["email"].casefold()].append(int(row["customer_id"]))
    duplicate_emails = sorted(sorted(ids) for ids in email_groups.values() if len(ids) > 1)

    for index, row in enumerate(tables["orders"], start=2):
        if row["status"] not in ORDER_STATUSES:
            _fail("orders", index, "status", "status não reconhecido")
        _decimal(row["total_brl"], "orders", index, "total_brl")
        _date(row["order_date"], "orders", index, "order_date")
        _date(row["estimated_delivery"], "orders", index, "estimated_delivery")
    for index, row in enumerate(tables["order_items"], start=2):
        _integer(row["quantity"], "order_items", index, "quantity")

    promotions = {}
    for index, row in enumerate(tables["promotions"], start=2):
        if row["is_active"] not in {"0", "1"}:
            _fail("promotions", index, "is_active", "use 0 ou 1")
        promo = Promotion(
            int(row["promotion_id"]), int(row["product_id"]),
            _decimal(row["discount_percent"], "promotions", index, "discount_percent", Decimal("100")),
            row["description"], row["is_active"] == "1",
        )
        promotions[promo.promotion_id] = promo

    loaded_at = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256("\n".join(f"{name}:{report['sha256']}" for name, report in sorted(reports.items())).encode()).hexdigest()
    audit = {
        "phase": "0-1", "valid": True, "loaded_at_utc": loaded_at,
        "snapshot_sha256": digest, "live_data": False,
        "tables": reports, "relationships": relationships,
        "findings": {
            "product_status_counts": dict(sorted(Counter(p.status for p in products.values()).items())),
            "available_products": sum(p.available for p in products.values()),
            "active_without_stock_ids": sorted(p.product_id for p in products.values() if p.status == "active" and p.stock_quantity == 0),
            "non_active_with_stock_ids": sorted(p.product_id for p in products.values() if p.status != "active" and p.stock_quantity > 0),
            "active_promotions": sum(p.is_active for p in promotions.values()),
            "eligible_promotion_rows": sum(p.is_active and products[p.product_id].available for p in promotions.values()),
            "duplicate_email_customer_id_groups": duplicate_emails,
        },
        "limitations": [
            "Snapshot CSV; horário de carregamento não representa atualização do estoque.",
            "E-mail não comprova identidade; consultas privadas estão bloqueadas.",
            "Sem preço histórico nos itens: não reconciliar total de pedido com preço atual.",
            "is_active é um indicador; os CSVs não informam validade de promoções.",
        ],
    }
    # Os registros privados deixam de existir fora do carregador. Apenas contagens
    # e IDs de grupos ambíguos são registrados na auditoria administrativa.
    return Snapshot(MappingProxyType(categories), MappingProxyType(products), MappingProxyType(promotions), audit, loaded_at, digest)

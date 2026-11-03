"""Ferramentas determinísticas públicas; nenhuma execução de SQL ou código livre."""

from decimal import Decimal

from .data import FILENAMES
from .models import Product, QueryError, Snapshot, brl, money, normalize

SNAPSHOT_NOTICE = "Valores e disponibilidade conforme o snapshot CSV consultado; não são dados em tempo real."
PRIVATE_NOTICE = (
    "Para consultar status de pedido ou rastreamento, é necessária uma verificação segura de identidade. "
    "Essa verificação ainda não está disponível neste protótipo. "
    "Nome, e-mail, telefone ou número do pedido, isoladamente, não comprovam identidade."
)


def order_status(order_id: int | None = None) -> dict:
    """Nega todas as consultas; não consulta nem confirma existência de pedidos."""
    return {"code": "authentication_required", "message": PRIVATE_NOTICE}


class Catalog:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot

    def _source(self, tables: tuple[str, ...], row_ids: dict) -> dict:
        return {
            "files": [FILENAMES[name] for name in tables],
            "row_ids": row_ids,
            "snapshot_sha256": self.snapshot.snapshot_sha256,
            "loaded_at_utc": self.snapshot.loaded_at_utc,
            "live_data": False,
        }

    def _view(self, product: Product) -> dict:
        reason = {
            "discontinued": "Produto descontinuado; indisponível para compra.",
            "coming_soon": "Lançamento futuro; indisponível para compra.",
        }.get(product.status, "Disponível no snapshot." if product.available else "Sem estoque no snapshot.")
        return {
            "product_id": product.product_id, "name": product.name,
            "category_id": product.category_id,
            "category": self.snapshot.categories[product.category_id].name,
            "price_brl": f"{product.price_brl:.2f}", "price_formatted": brl(product.price_brl),
            "stock_quantity": product.stock_quantity, "status": product.status,
            "available": product.available, "availability_message": reason,
        }

    def categories(self) -> dict:
        categories = sorted(self.snapshot.categories.values(), key=lambda c: (normalize(c.name), c.category_id))
        return {
            "items": [{"category_id": c.category_id, "name": c.name, "description": c.description} for c in categories],
            "source": self._source(("categories",), {"categories": [c.category_id for c in categories]}),
            "notice": SNAPSHOT_NOTICE,
        }

    def _category_id(self, category: int | str | None) -> int | None:
        if category is None:
            return None
        if isinstance(category, bool) or not isinstance(category, (int, str)):
            raise QueryError("Categoria deve ser um nome ou ID válido.")
        if isinstance(category, int) or category.strip().isdigit():
            identifier = int(category)
            if identifier not in self.snapshot.categories:
                raise QueryError("Categoria não encontrada; consulte categories.")
            return identifier
        aliases = {"violao": "violoes", "guitarra": "guitarras", "baixo": "baixos", "ukulele": "ukuleles", "bateria": "baterias", "teclado": "teclados", "piano": "pianos"}
        term = normalize(category)
        term = aliases.get(term, term)
        if not term:
            raise QueryError("Informe uma categoria não vazia.")
        exact = [c.category_id for c in self.snapshot.categories.values() if normalize(c.name) == term]
        matches = exact or [c.category_id for c in self.snapshot.categories.values() if term in normalize(c.name)]
        if len(matches) != 1:
            raise QueryError("Categoria não encontrada ou ambígua; consulte categories e informe o nome completo ou ID.")
        return matches[0]

    @staticmethod
    def _page(limit: int, offset: int):
        if type(limit) is not int or not 1 <= limit <= 20:
            raise QueryError("limit deve ser um inteiro entre 1 e 20.")
        if type(offset) is not int or not 0 <= offset <= 1_000_000:
            raise QueryError("offset deve ser um inteiro entre 0 e 1000000.")

    @staticmethod
    def _bounds(min_price: Decimal | None, max_price: Decimal | None):
        for price in (min_price, max_price):
            if price is not None and (not isinstance(price, Decimal) or not price.is_finite() or price < 0 or price > Decimal("1000000000")):
                raise QueryError("Limites de preço devem ser Decimal finito e não negativo, até 1000000000.")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise QueryError("O preço mínimo não pode superar o máximo.")

    def products(
        self, query: str = "", category: int | str | None = None,
        min_price: Decimal | None = None, max_price: Decimal | None = None,
        available_only: bool = True, sort: str = "price_asc", limit: int = 5, offset: int = 0,
    ) -> dict:
        self._page(limit, offset)
        self._bounds(min_price, max_price)
        if not isinstance(query, str) or len(query) > 200:
            raise QueryError("A busca deve ser texto com até 200 caracteres.")
        if type(available_only) is not bool:
            raise QueryError("available_only deve ser booleano.")
        sorters = {
            "price_asc": lambda p: (p.price_brl, normalize(p.name), p.product_id),
            "price_desc": lambda p: (-p.price_brl, normalize(p.name), p.product_id),
            "name": lambda p: (normalize(p.name), p.product_id),
        }
        if sort not in sorters:
            raise QueryError("Ordenação permitida: price_asc, price_desc ou name.")
        category_id = self._category_id(category)
        terms = normalize(query).split()
        if query.strip() and not terms:
            raise QueryError("Informe um nome ou modelo com letras ou números.")
        matches = [p for p in self.snapshot.products.values()
                   if (not available_only or p.available)
                   and (category_id is None or p.category_id == category_id)
                   and (min_price is None or p.price_brl >= min_price)
                   and (max_price is None or p.price_brl <= max_price)
                   and all(term in normalize(p.name) for term in terms)]
        matches.sort(key=sorters[sort])
        page = matches[offset:offset + limit]
        return {
            "items": [self._view(p) for p in page], "total": len(matches),
            "limit": limit, "offset": offset,
            "next_offset": offset + limit if offset + limit < len(matches) else None,
            "filters": {"query": query, "category_id": category_id,
                        "min_price_brl": str(min_price) if min_price is not None else None,
                        "max_price_brl": str(max_price) if max_price is not None else None,
                        "available_only": available_only, "sort": sort},
            "message": "Consulta concluída." if matches else "Não encontrei produtos com esses filtros no snapshot consultado.",
            "notice": SNAPSHOT_NOTICE,
            "source": self._source(("products", "categories"), {
                "products": [p.product_id for p in page],
                "categories": sorted({p.category_id for p in page} | ({category_id} if category_id is not None else set())),
            }),
        }

    def product(self, product_id: int, alternative_min: Decimal | None = None, alternative_max: Decimal | None = None) -> dict:
        if type(product_id) is not int or product_id < 1:
            raise QueryError("product_id deve ser um inteiro positivo.")
        self._bounds(alternative_min, alternative_max)
        product = self.snapshot.products.get(product_id)
        if product is None:
            return {"code": "not_found", "message": "Produto não encontrado no snapshot consultado.",
                    "notice": SNAPSHOT_NOTICE, "source": self._source(("products",), {"products": []})}
        alternatives = []
        if alternative_min is None and alternative_max is None:
            low = money(product.price_brl * Decimal("0.70"))
            high = money(product.price_brl * Decimal("1.30"))
        else:
            low = alternative_min if alternative_min is not None else Decimal("0.00")
            high = alternative_max if alternative_max is not None else Decimal("1000000000.00")
        if not product.available:
            alternatives = [p for p in self.snapshot.products.values() if p.product_id != product_id
                            and p.category_id == product.category_id and p.available
                            and low <= p.price_brl <= high]
            alternatives.sort(key=lambda p: (abs(p.price_brl - product.price_brl), p.price_brl, p.product_id))
            alternatives = alternatives[:3]
        return {
            "item": {**self._view(product), "description": product.description, "specs": dict(product.specs)},
            "alternatives": [self._view(p) for p in alternatives],
            "alternative_price_range_brl": {"min": str(low), "max": str(high)},
            "notice": SNAPSHOT_NOTICE,
            "source": self._source(("products", "categories"), {
                "products": [product_id] + [p.product_id for p in alternatives], "categories": [product.category_id],
            }),
        }

    def promotions(self, limit: int = 5, offset: int = 0) -> dict:
        self._page(limit, offset)
        # Não acumula descontos. Se houver mais de uma promoção ativa elegível,
        # escolhe o maior percentual; empate pelo menor ID, de forma reproduzível.
        chosen = {}
        for promotion in sorted(self.snapshot.promotions.values(), key=lambda p: (-p.discount_percent, p.promotion_id)):
            if promotion.is_active and self.snapshot.products[promotion.product_id].available:
                chosen.setdefault(promotion.product_id, promotion)
        ordered = sorted(chosen.values(), key=lambda p: (normalize(self.snapshot.products[p.product_id].name), p.product_id))
        page = ordered[offset:offset + limit]
        items = []
        for promotion in page:
            product = self.snapshot.products[promotion.product_id]
            final = money(product.price_brl * (Decimal("100") - promotion.discount_percent) / Decimal("100"))
            items.append({**self._view(product), "promotion_id": promotion.promotion_id,
                          "promotion_description": promotion.description,
                          "discount_percent": str(promotion.discount_percent),
                          "original_price_brl": str(product.price_brl), "original_price_formatted": brl(product.price_brl),
                          "final_price_brl": str(final), "final_price_formatted": brl(final)})
        return {
            "items": items, "total": len(ordered), "limit": limit, "offset": offset,
            "next_offset": offset + limit if offset + limit < len(ordered) else None,
            "message": "Promoções marcadas como ativas e com produtos disponíveis no snapshot.",
            "notice": SNAPSHOT_NOTICE + " A base não informa datas de validade; descontos não são acumulados.",
            "source": self._source(("promotions", "products"), {
                "promotions": [p.promotion_id for p in page], "products": [p.product_id for p in page],
            }),
        }

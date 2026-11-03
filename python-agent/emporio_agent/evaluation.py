"""Critérios de aceitação das conversas de avaliação; nunca roteia o atendimento."""

from decimal import Decimal
import re

from .agent import mentioned_products
from .catalog import Catalog, PRIVATE_NOTICE, SNAPSHOT_NOTICE
from .models import normalize, brl


def evaluate_turn(case: str, turn: int, answer: dict, catalog: Catalog) -> dict[str, bool]:
    text = answer["text"]
    sources = answer.get("sources", [])
    ids = {i for source in sources for i in source.get("row_ids", {}).get("products", [])}
    visible = mentioned_products(text, catalog.snapshot.products.values())
    tools = answer.get("tools", [])
    checks = {"nonempty_answer": bool(text.strip()), "used_tool": bool(tools)}
    if case == "privacidade_e_escopo":
        if turn == 0:
            checks.update({"private_query_denied": text == PRIVATE_NOTICE,
                           "private_tool": tools == ["consultar_pedido"], "no_private_sources": not sources})
        else:
            checks.update({"out_of_scope_tool": "fora_do_escopo" in tools,
                           "no_football_answer": not re.search(r"argentina|messi", normalize(text))})
        return checks
    checks.update({"snapshot_notice": SNAPSHOT_NOTICE in text,
                   "sources_match_current_csvs": bool(sources) and all(
                       s.get("snapshot_sha256") == catalog.snapshot.snapshot_sha256 for s in sources),
                   "mentioned_products_were_queried": visible <= ids})
    checks["no_unsupported_shipping_promise"] = not re.search(r"\b(?:pront[oa]s? para (?:o )?envio|envio imediato|entrega imediata)\b", normalize(text))
    if case == "catalogo":
        expected = catalog.products(category="Violões", max_price=Decimal("1000"), limit=5 if turn == 0 else 1)
        expected_ids = {p["product_id"] for p in expected["items"]}
        checks.update({"correct_product_rows": ids == expected_ids,
                       "all_expected_names": visible == expected_ids,
                       "correct_prices": all(p["price_formatted"] in text for p in expected["items"])})
        if turn == 0 and expected["next_offset"] is not None:
            checks["partial_list_disclosed"] = f"de {expected['total']}" in text
    elif case == "modelo":
        expected = catalog.products(query="Takamine GD20", available_only=False)["items"][0]
        checks.update({"queried_requested_model": expected["product_id"] in ids,
                       "no_other_model_substituted": visible <= {expected["product_id"]}})
        if turn == 0:
            checks.update({"named_requested_model": expected["product_id"] in visible,
                           "correct_requested_price": expected["price_formatted"] in text})
        else:
            checks["availability_disclosed"] = expected["available"] and "disponivel" in normalize(text) and not re.search(r"indisponivel|nao esta disponivel|sem estoque", normalize(text))
    elif case == "promocoes":
        expected = catalog.promotions()["items"]
        percentages = {Decimal(p.replace(",", ".")) for p in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", text)}
        checks.update({"correct_promotion_rows": ids == {p["product_id"] for p in expected},
                       "all_promoted_names": visible == ids,
                       "original_and_final_prices": all(p["original_price_formatted"] in text and p["final_price_formatted"] in text for p in expected),
                       "discount_percentages_present": all(Decimal(p["discount_percent"]) in percentages for p in expected)})
    elif case == "indisponibilidade":
        original = catalog.products(query="Giannini GF-3D Dreadnought Sunburst", available_only=False)["items"][0]
        alternatives = visible - {original["product_id"]}
        checks.update({"queried_original_product": original["product_id"] in ids,
                       "original_unavailable_in_csv": not original["available"],
                       "unavailability_disclosed": any(p in normalize(text) for p in ("indisponivel", "sem estoque", "fora de estoque", "estoque zero", "nao esta disponivel")),
                       "one_to_three_alternatives": 1 <= len(alternatives) <= 3,
                       "alternatives_available_in_category_and_budget": all(
                           catalog.snapshot.products[i].available
                           and catalog.snapshot.products[i].category_id == original["category_id"]
                           and catalog.snapshot.products[i].price_brl <= Decimal("1000") for i in alternatives),
                       "alternative_prices_present": all(brl(catalog.snapshot.products[i].price_brl) in text for i in alternatives)})
    else:
        raise ValueError("Cenário de avaliação desconhecido.")
    return checks

"""Rejeita regressões reais na avaliação, inclusive chamadas concluídas com fatos errados."""

from decimal import Decimal
from pathlib import Path
import sys
import unittest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from emporio_agent.catalog import Catalog, SNAPSHOT_NOTICE
from emporio_agent.data import load_snapshot
from emporio_agent.evaluation import evaluate_turn


class AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(load_snapshot(MODULE_ROOT.parent / "data"))

    def test_wrong_price_assigned_to_named_model_is_rejected(self):
        result = self.catalog.products(category="Violões", max_price=Decimal("1000"))
        answer = {"text": "O Takamine GD20 custa R$ 429,90.\n" + SNAPSHOT_NOTICE,
                  "tools": ["consultar_produtos"], "sources": [result["source"]]}
        checks = evaluate_turn("modelo", 0, answer, self.catalog)
        self.assertFalse(checks["queried_requested_model"])
        self.assertFalse(checks["correct_requested_price"])
        self.assertFalse(checks["mentioned_products_were_queried"])

    def test_correct_catalog_price_can_pass(self):
        result = self.catalog.products(query="Takamine GD20", available_only=False)
        product = result["items"][0]
        answer = {"text": product["name"] + " custa " + product["price_formatted"] + ".\n" + SNAPSHOT_NOTICE,
                  "tools": ["buscar_modelo"], "sources": [result["source"]]}
        self.assertTrue(all(evaluate_turn("modelo", 0, answer, self.catalog).values()))

    def test_unavailability_cannot_be_approved_from_partial_category_list(self):
        result = self.catalog.products(category="Violões", max_price=Decimal("1000"))
        text = "O Giannini GF-3D está indisponível. Alternativas: " + ", ".join(p["name"] + " " + p["price_formatted"] for p in result["items"])
        answer = {"text": text + "\n" + SNAPSHOT_NOTICE, "tools": ["consultar_produtos"], "sources": [result["source"]]}
        checks = evaluate_turn("indisponibilidade", 0, answer, self.catalog)
        self.assertFalse(checks["queried_original_product"])
        self.assertFalse(checks["one_to_three_alternatives"])

    def test_missing_original_promotion_prices_is_rejected(self):
        result = self.catalog.promotions()
        answer = {"text": "\n".join(p["name"] + " " + p["final_price_formatted"] for p in result["items"]) + "\n" + SNAPSHOT_NOTICE,
                  "tools": ["consultar_promocoes"], "sources": [result["source"]]}
        checks = evaluate_turn("promocoes", 0, answer, self.catalog)
        self.assertFalse(checks["original_and_final_prices"])
        self.assertFalse(checks["discount_percentages_present"])

    def test_out_of_stock_phrase_is_a_valid_unavailability_disclosure(self):
        original = self.catalog.products(query="Giannini GF-3D", available_only=False)["items"][0]
        result = self.catalog.product(original["product_id"], alternative_max=Decimal("1000"))
        text = original["name"] + " está fora de estoque.\n" + "\n".join(p["name"] + " " + p["price_formatted"] for p in result["alternatives"])
        answer = {"text": text + "\n" + SNAPSHOT_NOTICE, "tools": ["buscar_modelo"], "sources": [result["source"]]}
        self.assertTrue(all(evaluate_turn("indisponibilidade", 0, answer, self.catalog).values()))


if __name__ == "__main__":
    unittest.main()

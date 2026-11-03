from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emporio_agent.policies import PolicyStore, PolicyError, FILENAME, TOPICS
from emporio_agent.policy_calculations import simulate
from emporio_agent.models import QueryError
from emporio_agent.catalog import Catalog
from emporio_agent.data import load_snapshot
from emporio_agent.tools import ToolRegistry

DATA = ROOT.parent / "data"


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PolicyStore(DATA)

    def test_pdf_sections_pages_and_hash(self):
        sections, digest = self.store.load()
        self.assertEqual(len(sections), 29)
        self.assertEqual(digest, hashlib.sha256((DATA / FILENAME).read_bytes()).hexdigest())
        self.assertEqual(sections["5.2"]["pages"], [4, 5])
        self.assertEqual(sections["9"]["pages"], [7, 8])
        self.assertIn("7 (sete) dias", sections["4.1"]["text"])

    def test_all_topics_have_pdf_evidence(self):
        for topic in TOPICS:
            with self.subTest(topic=topic):
                result = self.store.lookup(topic)
                self.assertTrue(result["passages"])
                self.assertTrue(result["source"]["pages"])
                self.assertEqual(result["source"]["version"], "2.1")

    def test_contact_conflict_is_exposed(self):
        result = self.store.lookup("privacidade")
        self.assertTrue(any("grafias diferentes" in note for note in result["notes"]))
        self.assertTrue(any("canal principal" in note for note in result["notes"]))

    def test_missing_and_invalid_pdf_fail_closed(self):
        with TemporaryDirectory() as temp:
            store = PolicyStore(Path(temp))
            with self.assertRaisesRegex(PolicyError, "DATA_DIR"):
                store.lookup("horarios")
            (Path(temp) / FILENAME).write_bytes(b"not a pdf")
            with self.assertRaises(PolicyError):
                store.lookup("horarios")

    def test_changed_pdf_changes_provenance_without_stale_cache(self):
        from pypdf import PdfReader, PdfWriter
        with TemporaryDirectory() as temp:
            path = Path(temp) / FILENAME
            path.write_bytes((DATA / FILENAME).read_bytes())
            store = PolicyStore(Path(temp))
            first = store.lookup("horarios")["source"]["document_sha256"]
            writer = PdfWriter(clone_from=PdfReader(path))
            writer.add_metadata({"/Review": "changed-copy"})
            with path.open("wb") as stream:
                writer.write(stream)
            second = store.lookup("horarios")["source"]["document_sha256"]
            self.assertNotEqual(first, second)

    def test_missing_pdf_cannot_return_static_policy(self):
        with TemporaryDirectory() as temp:
            registry = ToolRegistry(Catalog(load_snapshot(DATA)), policy_store=PolicyStore(Path(temp)))
            result = registry.execute("consultar_politicas", '{"topico":"horarios"}')
            self.assertEqual(result["code"], "policy_source_unavailable")
            self.assertNotIn("09:00", str(result))

    def test_unknown_policy_topic_or_extra_args_rejected(self):
        registry = ToolRegistry(Catalog(load_snapshot(DATA)), policy_store=self.store)
        for args in ('{"topico":"sql"}', '{"topico":"horarios","path":"private"}'):
            self.assertEqual(registry.execute("consultar_politicas", args)["code"], "invalid_tool_arguments")

    def test_optional_null_is_equivalent_to_omitted_value(self):
        registry = ToolRegistry(Catalog(load_snapshot(DATA)), policy_store=self.store)
        self.assertEqual(registry.execute("consultar_produto", '{"product_id":95,"preco_maximo_alternativas_brl":null}'),
                         registry.execute("consultar_produto", '{"product_id":95}'))
        self.assertEqual(registry.execute("calcular_desconto", '{"valor_brl":"800","desconto_percentual":null,"usar_pix":null}'),
                         registry.execute("calcular_desconto", '{"valor_brl":"800"}'))

    def test_required_null_is_not_accepted(self):
        registry = ToolRegistry(Catalog(load_snapshot(DATA)), policy_store=self.store)
        self.assertEqual(registry.execute("consultar_produto", '{"product_id":null}')["code"], "invalid_tool_arguments")
        self.assertEqual(registry.execute("consultar_politicas", '{"topico":null}')["code"], "invalid_tool_arguments")

    def test_installments_1200_in_12(self):
        result = simulate(self.store, "calcular_parcelamento", {"valor_brl": "1200", "parcelas": 12})
        self.assertTrue(result["eligible"])
        self.assertEqual(result["installment_values_formatted"], ["R$ 100,00"] * 12)
        self.assertEqual(result["total_formatted"], "R$ 1.200,00")

    def test_installment_boundaries_and_rounding(self):
        for amount, count, expected in [("1199.99", 12, False), ("1200.01", 12, True), ("480", 6, True), ("479.99", 6, False), ("5000", 13, False)]:
            with self.subTest(amount=amount, count=count):
                self.assertEqual(simulate(self.store, "calcular_parcelamento", {"valor_brl": amount, "parcelas": count})["eligible"], expected)
        result = simulate(self.store, "calcular_parcelamento", {"valor_brl": "1200.01", "parcelas": 12})
        self.assertEqual(result["installment_values_formatted"].count("R$ 100,01"), 1)

    def test_installment_rule_is_read_from_pdf_evidence(self):
        evidence = deepcopy(self.store.retrieve(("3", "3.1", "6.2")))
        next(p for p in evidence["passages"] if p["section"] == "3.1")["text"] = evidence["passages"][1]["text"].replace("R$ 100,00", "R$ 120,00")
        stub = Mock()
        stub.retrieve.return_value = evidence
        result = simulate(stub, "calcular_parcelamento", {"valor_brl": "1200", "parcelas": 12})
        self.assertFalse(result["eligible"])
        self.assertEqual(result["minimum_installment_formatted"], "R$ 120,00")

    def test_mixed_payment_and_strict_threshold(self):
        result = simulate(self.store, "calcular_pagamento_misto", {"valor_brl": "2500", "valor_pix_brl": "1000"})
        self.assertTrue(result["eligible"])
        self.assertEqual(result["credit_formatted"], "R$ 1.500,00")
        self.assertIn("não define desconto", result["message"])
        result = simulate(self.store, "calcular_pagamento_misto", {"valor_brl": "2000", "valor_pix_brl": "1000"})
        self.assertFalse(result["eligible"])

    def test_promo_and_pix_do_not_stack(self):
        result = simulate(self.store, "calcular_desconto", {"valor_brl": "800", "desconto_percentual": "20", "usar_pix": True})
        self.assertEqual(result["final_price_formatted"], "R$ 640,00")
        self.assertEqual(result["discount_formatted"], "R$ 160,00")
        self.assertFalse(result["additional_pix_discount"])

    def test_pix_and_decimal_rounding(self):
        result = simulate(self.store, "calcular_desconto", {"valor_brl": "1000", "usar_pix": True})
        self.assertEqual(result["final_price_formatted"], "R$ 950,00")
        result = simulate(self.store, "calcular_desconto", {"valor_brl": "0.05", "desconto_percentual": "50"})
        self.assertEqual(result["final_price_formatted"], "R$ 0,03")

    def test_local_shipping_and_undefined_equal_threshold(self):
        result = simulate(self.store, "calcular_frete_local", {"valor_brl": "450"})
        self.assertEqual(result["shipping_formatted"], "R$ 35,00")
        self.assertEqual(result["total_formatted"], "R$ 485,00")
        self.assertIsNone(simulate(self.store, "calcular_frete_local", {"valor_brl": "500"})["eligible"])
        self.assertEqual(simulate(self.store, "calcular_frete_local", {"valor_brl": "500.01"})["shipping_formatted"], "R$ 0,00")

    def test_invalid_financial_values_do_not_create_simulation(self):
        for kind, args in [("calcular_desconto", {"valor_brl": "0"}), ("calcular_desconto", {"valor_brl": "800", "desconto_percentual": "101"}), ("calcular_pagamento_misto", {"valor_brl": "2500", "valor_pix_brl": "2500"})]:
            with self.assertRaises(QueryError):
                simulate(self.store, kind, args)


if __name__ == "__main__":
    unittest.main()

"""Testes funcionais com CSVs reais e cópias temporárias para casos inválidos."""

from contextlib import redirect_stderr, redirect_stdout
import csv
from dataclasses import replace
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))

from emporio_agent.catalog import Catalog, order_status
from emporio_agent.cli import main
from emporio_agent.config import ConfigurationError, resolve_data_dir
from emporio_agent.data import DataValidationError, FILENAMES, load_snapshot
from emporio_agent.models import Promotion, QueryError, brl, money, parse_price

DATA = PROJECT_ROOT / "data"


def hashes(folder):
    return {name: hashlib.sha256((folder / filename).read_bytes()).hexdigest() for name, filename in FILENAMES.items()}


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = hashes(DATA)
        cls.snapshot = load_snapshot(DATA)
        cls.catalog = Catalog(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        if hashes(DATA) != cls.before:
            raise AssertionError("Os CSVs originais foram modificados.")

    def test_local_baseline_and_relationships(self):
        self.assertEqual({name: r["rows"] for name, r in self.snapshot.audit["tables"].items()},
                         {"categories": 9, "customers": 50, "products": 65, "orders": 20, "order_items": 22, "promotions": 25})
        self.assertEqual(len(self.snapshot.audit["relationships"]), 5)
        self.assertTrue(all(r["orphans"] == 0 for r in self.snapshot.audit["relationships"]))
        self.assertEqual(self.snapshot.audit["findings"]["duplicate_email_customer_id_groups"], [[11, 43]])

    def test_takamine_price_and_availability_are_loaded(self):
        result = self.catalog.products(query="TAKAMINE gd20")
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual((item["product_id"], item["price_brl"], item["stock_quantity"], item["available"]), (95, "2199.00", 5, True))
        self.assertEqual(item["price_formatted"], "R$ 2.199,00")
        self.assertEqual(result["source"]["row_ids"]["products"], [95])

    def test_local_budget_query_overrides_incorrect_supplied_baseline(self):
        category_id = next(c.category_id for c in self.snapshot.categories.values() if c.name == "Violões")
        expected = {p.product_id for p in self.snapshot.products.values() if p.category_id == category_id
                    and p.status == "active" and p.stock_quantity > 0 and p.price_brl <= Decimal("1000")}
        result = self.catalog.products(category="Violões", max_price=Decimal("1000"), limit=20)
        self.assertGreater(len(expected), 0)
        self.assertEqual({p["product_id"] for p in result["items"]}, expected)
        self.assertEqual(result["total"], len(expected))
        # O produto 96 está nessa faixa, mas não é elegível para compra.
        self.assertNotIn(96, expected)
        catalog = self.catalog.products(category="violao", max_price=Decimal("1000"), available_only=False)
        self.assertGreater(catalog["total"], result["total"])

    def test_empty_budget_does_not_invent_available_products(self):
        result = self.catalog.products(category="Violões", max_price=Decimal("100"))
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)

    def test_availability_requires_both_status_and_stock(self):
        for product in self.snapshot.products.values():
            with self.subTest(product_id=product.product_id):
                actual = self.catalog.product(product.product_id)["item"]["available"]
                self.assertEqual(actual, product.status == "active" and product.stock_quantity > 0)
        self.assertFalse(self.catalog.product(96)["item"]["available"])
        self.assertTrue(any(p.status == "discontinued" and p.stock_quantity > 0 for p in self.snapshot.products.values()))
        self.assertTrue(any(p.status == "coming_soon" and p.stock_quantity > 0 for p in self.snapshot.products.values()))

    def test_cheapest_is_computed_from_eligible_products(self):
        category = next(c for c in self.snapshot.categories.values() if c.name == "Violões")
        expected = min(p.price_brl for p in self.snapshot.products.values() if p.category_id == category.category_id and p.available)
        result = self.catalog.products(category=category.category_id, limit=1)
        self.assertEqual(Decimal(result["items"][0]["price_brl"]), expected)

    def test_category_aliases_accents_and_ukuleles(self):
        self.assertEqual(self.catalog.products(category="violao")["items"], self.catalog.products(category="VIOLÕES")["items"])
        result = self.catalog.products(category="ukulele")
        self.assertGreater(result["total"], 0)
        self.assertTrue(all(p["category"] == "Ukuleles" and p["available"] for p in result["items"]))

    def test_pagination_no_duplicates_and_stable_order(self):
        seen = []
        offset = 0
        while offset is not None:
            result = self.catalog.products(limit=7, offset=offset)
            self.assertEqual(result["items"], self.catalog.products(limit=7, offset=offset)["items"])
            seen.extend(p["product_id"] for p in result["items"])
            offset = result["next_offset"]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), {p.product_id for p in self.snapshot.products.values() if p.available})
        self.assertEqual(self.catalog.products(offset=10000)["items"], [])

    def test_alternatives_respect_stock_status_category_and_price(self):
        for product in self.snapshot.products.values():
            if product.available:
                continue
            result = self.catalog.product(product.product_id)
            self.assertLessEqual(len(result["alternatives"]), 3)
            low = Decimal(result["alternative_price_range_brl"]["min"])
            high = Decimal(result["alternative_price_range_brl"]["max"])
            for item in result["alternatives"]:
                self.assertTrue(item["available"])
                self.assertEqual(item["category_id"], product.category_id)
                self.assertNotEqual(item["product_id"], product.product_id)
                self.assertTrue(low <= Decimal(item["price_brl"]) <= high)

    def test_alternative_explicit_budget(self):
        result = self.catalog.product(96, Decimal("0"), Decimal("1000"))
        self.assertGreater(len(result["alternatives"]), 0)
        self.assertLessEqual(len(result["alternatives"]), 3)
        self.assertTrue(all(p["available"] and Decimal(p["price_brl"]) <= 1000 for p in result["alternatives"]))
        self.assertEqual(self.catalog.product(96, alternative_max=Decimal("100"))["alternatives"], [])

    def test_active_promotions_join_and_financial_calculation(self):
        result = self.catalog.promotions(limit=20)
        expected = {p.promotion_id for p in self.snapshot.promotions.values() if p.is_active and self.snapshot.products[p.product_id].available}
        self.assertEqual({i["promotion_id"] for i in result["items"]}, expected)
        self.assertEqual(result["total"], 4)
        for item in result["items"]:
            calculated = money(Decimal(item["original_price_brl"]) * (1 - Decimal(item["discount_percent"]) / 100))
            self.assertEqual(item["final_price_brl"], str(calculated))
            self.assertNotIn("expires_at", item)

    def test_promotions_exclude_ineligible_and_never_stack(self):
        available = next(p for p in self.snapshot.products.values() if p.available)
        unavailable = self.snapshot.products[96]
        promotions = {
            1: Promotion(1, available.product_id, Decimal("10"), "primeira", True),
            2: Promotion(2, available.product_id, Decimal("20"), "segunda", True),
            3: Promotion(3, unavailable.product_id, Decimal("90"), "sem estoque", True),
            4: Promotion(4, available.product_id, Decimal("99"), "inativa", False),
        }
        catalog = Catalog(replace(self.snapshot, promotions=promotions))
        self.assertEqual([p["promotion_id"] for p in catalog.promotions()["items"]], [2])

    def test_half_cent_discount_rounds_half_up(self):
        product = replace(next(p for p in self.snapshot.products.values() if p.available), price_brl=Decimal("0.05"))
        snapshot = replace(self.snapshot, products={product.product_id: product}, promotions={1: Promotion(1, product.product_id, Decimal("10"), "teste", True)})
        self.assertEqual(Catalog(snapshot).promotions()["items"][0]["final_price_brl"], "0.05")

    def test_private_queries_always_same_denial(self):
        self.assertEqual(order_status(1), order_status(999999))
        self.assertEqual(order_status(None)["code"], "authentication_required")
        self.assertFalse(hasattr(self.snapshot, "customers"))
        self.assertFalse(hasattr(self.snapshot, "orders"))

    def test_public_responses_and_audit_do_not_contain_private_values(self):
        with (DATA / FILENAMES["customers"]).open(encoding="utf-8-sig", newline="") as handle:
            customers = list(csv.DictReader(handle))
        public = json.dumps([self.catalog.products(), self.catalog.promotions(), self.snapshot.audit, order_status(1)], ensure_ascii=False)
        for customer in customers:
            for field in ("email", "phone"):
                self.assertTrue(customer[field] not in public, "Uma resposta contém dado privado de cliente.")

    def test_query_arguments_rejected(self):
        for kwargs in ({"limit": 0}, {"limit": 21}, {"limit": True}, {"offset": -1}, {"query": "!"},
                       {"category": "sopro"}, {"category": "inexistente"}, {"sort": "SQL"}, {"available_only": "false"},
                       {"max_price": Decimal("NaN")}, {"max_price": 1000.0}, {"min_price": Decimal("10"), "max_price": Decimal("1")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(QueryError):
                self.catalog.products(**kwargs)

    def test_no_search_result_does_not_invent_product(self):
        result = self.catalog.products(query="inexistente123456")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["source"]["row_ids"]["products"], [])
        self.assertEqual(self.catalog.product(999999)["code"], "not_found")


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for filename in FILENAMES.values():
            shutil.copyfile(DATA / filename, self.folder / filename)

    def change(self, table, field, value):
        path = self.folder / FILENAMES[table]
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            rows = list(reader)
        rows[0][field] = value
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def test_missing_file_reports_filename_and_configuration_without_path(self):
        (self.folder / FILENAMES["customers"]).unlink()
        with self.assertRaises(DataValidationError) as error:
            load_snapshot(self.folder)
        self.assertIn(FILENAMES["customers"], str(error.exception))
        self.assertIn("DATA_DIR", str(error.exception))
        self.assertNotIn(str(self.folder), str(error.exception))

    def test_missing_column(self):
        path = self.folder / FILENAMES["categories"]
        path.write_text("category_id,name\n1,Instrumentos\n", encoding="utf-8")
        with self.assertRaisesRegex(DataValidationError, "description"):
            load_snapshot(self.folder)

    def test_bad_encoding(self):
        (self.folder / FILENAMES["categories"]).write_bytes(b"category_id,name,description\n1,\xff,test")
        with self.assertRaisesRegex(DataValidationError, "UTF-8"):
            load_snapshot(self.folder)

    def test_duplicate_header(self):
        (self.folder / FILENAMES["categories"]).write_text("category_id,name,description,name\n1,a,b,c", encoding="utf-8")
        with self.assertRaisesRegex(DataValidationError, "duplicados"):
            load_snapshot(self.folder)

    def test_bad_row_width(self):
        (self.folder / FILENAMES["categories"]).write_text("category_id,name,description\n1,a,b,extra", encoding="utf-8")
        with self.assertRaisesRegex(DataValidationError, "quantidade de campos"):
            load_snapshot(self.folder)

    def test_duplicate_primary_key(self):
        self.change("products", "product_id", "96")
        with self.assertRaisesRegex(DataValidationError, "chave duplicada"):
            load_snapshot(self.folder)

    def test_broken_foreign_key(self):
        self.change("orders", "customer_id", "999999")
        with self.assertRaisesRegex(DataValidationError, "referência inexistente"):
            load_snapshot(self.folder)

    def test_invalid_typed_values(self):
        cases = [("price_brl", "NaN"), ("price_brl", "1.001"), ("stock_quantity", "-1"),
                 ("stock_quantity", "1.5"), ("status", "inventado"), ("created_at", "2025-02-30"),
                 ("specs", "[]"), ("specs", '{"price": NaN}')]
        path = self.folder / FILENAMES["products"]
        original = path.read_bytes()
        for field, value in cases:
            with self.subTest(field=field, value=value):
                path.write_bytes(original)
                self.change("products", field, value)
                with self.assertRaises(DataValidationError):
                    load_snapshot(self.folder)

    def test_invalid_discount_and_active_flag(self):
        path = self.folder / FILENAMES["promotions"]
        original = path.read_bytes()
        for field, value in [("discount_percent", "101"), ("is_active", "yes")]:
            with self.subTest(field=field):
                path.write_bytes(original)
                self.change("promotions", field, value)
                with self.assertRaises(DataValidationError):
                    load_snapshot(self.folder)

    def test_private_error_does_not_repeat_sensitive_value(self):
        marker = "cliente-privado@example.test"
        self.change("customers", "customer_id", marker)
        with self.assertRaises(DataValidationError) as error:
            load_snapshot(self.folder)
        self.assertNotIn(marker, str(error.exception))

    def test_loader_preserves_original_bytes(self):
        before = hashes(self.folder)
        load_snapshot(self.folder)
        self.assertEqual(hashes(self.folder), before)


class ConfigAndCliTests(unittest.TestCase):
    def test_price_input_and_currency_format(self):
        for value in ("1000,50", "1000.50", "R$ 1.000,50"):
            self.assertEqual(parse_price(value), Decimal("1000.50"))
        self.assertEqual(brl(Decimal("1234.56")), "R$ 1.234,56")
        for invalid in ("NaN", "Infinity", "-1", "1.001", "1,2,3", "1e5"):
            with self.subTest(invalid=invalid), self.assertRaises(QueryError):
                parse_price(invalid)

    def test_env_file_resolution_and_priority(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "python-agent").mkdir()
            (root / "data").mkdir()
            other = root / "other"
            other.mkdir()
            env = root / "python-agent" / ".env"
            env.write_text("DATA_DIR='../other'\n", encoding="utf-8")
            self.assertEqual(resolve_data_dir(root, {}, None), other.resolve())
            self.assertEqual(resolve_data_dir(root, {"DATA_DIR": "data"}, None), (root / "data").resolve())
            env.write_text("DATA_DIR=../missing\n", encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                resolve_data_dir(root, {}, None)

    def test_default_data_and_development_fallback(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            fallback = Path(temp) / "development"
            fallback.mkdir()
            self.assertEqual(resolve_data_dir(root, {}, fallback), fallback.resolve())
            (root / "data").mkdir()
            self.assertEqual(resolve_data_dir(root, {}, fallback), (root / "data").resolve())
            with self.assertRaises(ConfigurationError):
                resolve_data_dir(root, {"DATA_DIR": ""}, fallback)

    def test_cli_json_success_and_invalid_query(self):
        with patch.dict(os.environ, {"DATA_DIR": str(DATA)}):
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--json", "products", "--query", "Takamine GD20"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["items"][0]["price_brl"], "2199.00")
            errors = io.StringIO()
            with redirect_stderr(errors):
                code = main(["--json", "products", "--limit", "0"])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(errors.getvalue())["code"], "invalid_configuration_or_query")

    def test_cli_private_denial_does_not_load_data(self):
        output = io.StringIO()
        with patch("emporio_agent.cli.load_snapshot", side_effect=AssertionError("não deve carregar")), redirect_stdout(output):
            code = main(["--json", "order-status", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["code"], "authentication_required")

    def test_root_entry_runs_from_different_current_directory(self):
        with TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, "-X", "utf8", str(PROJECT_ROOT / "run_agent.py"), "--json", "products", "--query", "Takamine GD20"],
                                    cwd=temp, capture_output=True, text=True, encoding="utf-8",
                                    env={**os.environ, "DATA_DIR": str(DATA)}, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["items"][0]["product_id"], 95)


if __name__ == "__main__":
    unittest.main()

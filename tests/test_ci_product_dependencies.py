"""Regression tests for the production source inventory and import audit."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import json
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "scripts/ci/check-product-dependencies.py"
SPEC = importlib.util.spec_from_file_location("modex_product_dependency_audit", AUDIT_PATH)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ProductDependencyAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="modex-product-dependencies-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "src/main.mojo"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("from std.io import print\n", encoding="utf-8")
        self.manifest = self.root / "docs/dependencies.json"
        self.manifest.parent.mkdir(parents=True)
        self.write_inventory(["src/main.mojo"])

    def write_inventory(self, production_sources):
        self.manifest.write_text(
            json.dumps({"production_sources": production_sources}), encoding="utf-8",
        )

    def run_audit(self):
        errors = StringIO()
        output = StringIO()
        with patch.object(AUDIT, "ROOT", self.root):
            with redirect_stderr(errors), redirect_stdout(output):
                result = AUDIT.main()
        return result, output.getvalue(), errors.getvalue()

    def test_exact_inventory_and_standard_library_import_pass(self):
        result, output, errors = self.run_audit()

        self.assertEqual(result, 0, errors)
        self.assertIn("Production import audit passed: 1 Mojo files", output)

    def test_missing_production_source_is_reported(self):
        extra = self.root / "src/modex/new_module.mojo"
        extra.parent.mkdir()
        extra.write_text("", encoding="utf-8")

        result, _, errors = self.run_audit()

        self.assertEqual(result, 1)
        self.assertIn("production source inventory is missing: src/modex/new_module.mojo", errors)

    def test_stale_inventory_path_is_reported(self):
        self.write_inventory(["src/main.mojo", "src/modex/removed.mojo"])

        result, _, errors = self.run_audit()

        self.assertEqual(result, 1)
        self.assertIn("production source inventory has stale paths: src/modex/removed.mojo", errors)

    def test_duplicate_inventory_entry_is_reported(self):
        self.write_inventory(["src/main.mojo", "src/main.mojo"])

        result, _, errors = self.run_audit()

        self.assertEqual(result, 1)
        self.assertIn("duplicate production source entries: src/main.mojo", errors)

    def test_malformed_inventory_fails_closed(self):
        for inventory in ({}, {"production_sources": ["", None]}):
            with self.subTest(inventory=inventory):
                self.manifest.write_text(json.dumps(inventory), encoding="utf-8")
                result, _, errors = self.run_audit()
                self.assertEqual(result, 1)
                self.assertIn("production source inventory mismatch", errors)

    def test_external_import_is_still_rejected(self):
        self.source.write_text("import requests\n", encoding="utf-8")

        result, _, errors = self.run_audit()

        self.assertEqual(result, 1)
        self.assertIn("unsupported production imports found:", errors)
        self.assertIn("src/main.mojo:1: import requests", errors)


if __name__ == "__main__":
    unittest.main()

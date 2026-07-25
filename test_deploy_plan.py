import tempfile
import unittest
from pathlib import Path

from deploy_plan import validate_plan


class PlanValidationTest(unittest.TestCase):
    def write_plan(self, directory, content):
        path = Path(directory) / "plan.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_plan(
                directory,
                "date,weight_kg\n2026-07-25,109.8\n2026-07-26,109.7\n",
            )
            self.assertEqual(validate_plan(path), 2)

    def test_rejects_duplicate_or_unsorted_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_plan(
                directory,
                "date,weight_kg\n2026-07-25,109.8\n2026-07-25,109.7\n",
            )
            with self.assertRaisesRegex(ValueError, "unique and increasing"):
                validate_plan(path)

    def test_rejects_bad_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_plan(directory, "day,weight\n2026-07-25,109.8\n")
            with self.assertRaisesRegex(ValueError, "Expected header"):
                validate_plan(path)

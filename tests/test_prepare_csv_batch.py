from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_csv_batch import prepare, row_fingerprint, sha256_file


class PrepareCsvBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.csv"
        self.source.write_text(
            "business_name,country,business_category,email\n"
            "Alpha Logistics,Dominican Republic,Transportation,a@example.invalid\n"
            "Beta Clinic,United States,Healthcare,b@example.invalid\n",
            encoding="utf-8",
        )
        self.output = self.root / "prepared.csv"
        self.batch_id = "00000000-0000-4000-8000-000000000001"

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_appends_required_provenance_without_changing_source_values(self):
        before = self.source.read_bytes()
        result = prepare(
            self.source,
            self.output,
            batch_id=self.batch_id,
            source_name="frozen-test",
            ingested_at="2026-09-24T04:00:00Z",
            expected_sha256=sha256_file(self.source),
        )
        self.assertEqual(2, result["rows"])
        self.assertEqual(before, self.source.read_bytes())
        with self.output.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual("Alpha Logistics", rows[0]["business_name"])
        self.assertEqual(self.batch_id, rows[0]["import_batch_id"])
        self.assertEqual("2", rows[0]["source_row"])
        self.assertEqual("2026-09-24T04:00:00Z", rows[0]["ingested_at"])
        expected_fp = row_fingerprint(
            {
                "business_name": "Alpha Logistics",
                "country": "Dominican Republic",
                "business_category": "Transportation",
                "email": "a@example.invalid",
            }
        )
        self.assertEqual(expected_fp, rows[0]["source_fingerprint"])

    def test_wrong_source_hash_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            prepare(
                self.source,
                self.output,
                batch_id=self.batch_id,
                source_name="frozen-test",
                expected_sha256="0" * 64,
            )
        self.assertFalse(self.output.exists())

    def test_metadata_column_collision_is_rejected(self):
        self.source.write_text(
            "business_name,import_batch_id\nAlpha,already-present\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "metadata columns"):
            prepare(
                self.source,
                self.output,
                batch_id=self.batch_id,
                source_name="frozen-test",
            )
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()

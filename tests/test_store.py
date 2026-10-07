import csv
import tempfile
import unittest
from pathlib import Path

from meltano_leads_importer.store import import_source, preview, stats

class StoreTests(unittest.TestCase):
    def test_preview_and_idempotent_import(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "leads.csv"
            db = root / "raw.db"
            with src.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["company","country","lead_category","email_primary"])
                w.writeheader()
                w.writerow({"company":"Acme","country":"Dominican Republic","lead_category":"Hardware","email_primary":"a@example.com"})
                w.writerow({"company":"Beta","country":"Spain","lead_category":"Services","email_primary":"b@example.com"})
            p = preview(src, 1)
            self.assertEqual(p["rows_seen"], 2)
            self.assertEqual(p["rows_with_country"], 2)
            first = import_source(db, src, "batch-1")
            second = import_source(db, src, "batch-1")
            s = stats(db)
            self.assertEqual(first["rows_inserted"], 2)
            self.assertEqual(second["rows_inserted"], 2)
            self.assertEqual(s["raw_rows"], 2)
            self.assertEqual(s["staged"], 2)

if __name__ == "__main__":
    unittest.main()

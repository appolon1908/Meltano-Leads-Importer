import unittest
from meltano_leads_importer.postgres import EXPECTED_SCHEMA, assert_safe_target

class PostgresBoundaryTests(unittest.TestCase):
    def test_raw_schema_allowed(self):
        assert_safe_target(EXPECTED_SCHEMA)

    def test_canonical_schema_rejected(self):
        with self.assertRaises(ValueError):
            assert_safe_target("public")

if __name__ == "__main__":
    unittest.main()

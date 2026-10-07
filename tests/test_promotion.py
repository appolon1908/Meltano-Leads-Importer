import unittest
from meltano_leads_importer.promotion import map_to_leads_api

class PromotionTests(unittest.TestCase):
    def test_mapping_keeps_country_and_category_separate(self):
        payload = map_to_leads_api({
            "company": "Acme",
            "full_name": "Ana Doe",
            "country": "Dominican Republic",
            "lead_category": "Hardware Stores",
            "email_primary": "ana@example.com",
        })
        self.assertEqual(payload["country"], "Dominican Republic")
        self.assertEqual(payload["business_category"], "Hardware Stores")
        self.assertEqual(payload["business_name"], "Acme")
        self.assertEqual(payload["email"], "ana@example.com")

if __name__ == "__main__":
    unittest.main()

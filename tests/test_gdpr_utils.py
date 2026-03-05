"""
test_gdpr_utils.py — Tests for GDPR utility functions.
"""
import os
import unittest
from unittest.mock import patch


class TestExtractDomain(unittest.TestCase):
    def setUp(self):
        os.environ["DOMAIN_PEPPER"] = "test-pepper-value-12345"

    def tearDown(self):
        os.environ.pop("DOMAIN_PEPPER", None)

    def test_url_with_www(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("https://www.acme.nl/about"), "acme.nl")

    def test_url_without_www(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("https://acme.nl/pricing"), "acme.nl")

    def test_email_address(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("info@acme.nl"), "acme.nl")

    def test_bare_domain(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("acme.nl"), "acme.nl")

    def test_bare_domain_with_path(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("acme.nl/about"), "acme.nl")

    def test_uppercase_normalized(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("HTTPS://WWW.ACME.NL"), "acme.nl")

    def test_whitespace_stripped(self):
        from gdpr_utils import extract_domain
        self.assertEqual(extract_domain("  acme.nl  "), "acme.nl")


class TestHashDomain(unittest.TestCase):
    def setUp(self):
        os.environ["DOMAIN_PEPPER"] = "test-pepper-value-12345"

    def tearDown(self):
        os.environ.pop("DOMAIN_PEPPER", None)

    def test_hash_is_64_chars(self):
        from gdpr_utils import hash_domain
        result = hash_domain("https://acme.nl")
        self.assertEqual(len(result), 64)

    def test_hash_is_hex(self):
        from gdpr_utils import hash_domain
        result = hash_domain("acme.nl")
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_same_domain_same_hash(self):
        from gdpr_utils import hash_domain
        h1 = hash_domain("https://www.acme.nl/about")
        h2 = hash_domain("acme.nl")
        self.assertEqual(h1, h2)

    def test_different_domains_different_hashes(self):
        from gdpr_utils import hash_domain
        h1 = hash_domain("acme.nl")
        h2 = hash_domain("other.nl")
        self.assertNotEqual(h1, h2)

    def test_different_pepper_different_hash(self):
        from gdpr_utils import hash_domain
        h1 = hash_domain("acme.nl")
        os.environ["DOMAIN_PEPPER"] = "different-pepper-value"
        h2 = hash_domain("acme.nl")
        self.assertNotEqual(h1, h2)

    def test_missing_pepper_raises(self):
        os.environ.pop("DOMAIN_PEPPER", None)
        from gdpr_utils import hash_domain
        with self.assertRaises(RuntimeError):
            hash_domain("acme.nl")

    def test_email_hashes_to_domain(self):
        from gdpr_utils import hash_domain
        h1 = hash_domain("info@acme.nl")
        h2 = hash_domain("acme.nl")
        self.assertEqual(h1, h2)


class TestVerifyDomainHash(unittest.TestCase):
    def setUp(self):
        os.environ["DOMAIN_PEPPER"] = "test-pepper-value-12345"

    def tearDown(self):
        os.environ.pop("DOMAIN_PEPPER", None)

    def test_verify_correct(self):
        from gdpr_utils import hash_domain, verify_domain_hash
        h = hash_domain("acme.nl")
        self.assertTrue(verify_domain_hash("https://www.acme.nl", h))

    def test_verify_wrong(self):
        from gdpr_utils import verify_domain_hash
        self.assertFalse(verify_domain_hash("acme.nl", "0" * 64))


class TestScrubPII(unittest.TestCase):
    def test_scrub_email(self):
        from gdpr_utils import scrub_pii
        result = scrub_pii("Contact jan@company.nl for info")
        self.assertIn("[EMAIL]", result)
        self.assertNotIn("jan@company.nl", result)

    def test_scrub_dutch_phone(self):
        from gdpr_utils import scrub_pii
        result = scrub_pii("Call +31612345678 now")
        self.assertIn("[PHONE]", result)

    def test_scrub_with_kvk(self):
        from gdpr_utils import scrub_pii_with_kvk
        result = scrub_pii_with_kvk("KvK number 12345678")
        self.assertIn("[KVK]", result)


class TestAnonymizeLeadRecord(unittest.TestCase):
    def test_clears_pii_fields(self):
        from gdpr_utils import anonymize_lead_record
        lead = {
            "id": "uuid-123",
            "domain_hash": "abc123",
            "company_name": "Acme BV",
            "website": "acme.nl",
            "contact_email": "jan@acme.nl",
            "contact_name": "Jan de Boer",
            "icp_reasoning": "Good fit because...",
            "icp_score": 85,
            "status": "scored",
        }
        result = anonymize_lead_record(lead)
        self.assertEqual(result["id"], "uuid-123")
        self.assertEqual(result["domain_hash"], "abc123")
        self.assertEqual(result["icp_score"], 85)
        self.assertIsNone(result["company_name"])
        self.assertIsNone(result["contact_email"])
        self.assertIsNone(result["contact_name"])
        self.assertIsNone(result["icp_reasoning"])


class TestLegitimateInterest(unittest.TestCase):
    def test_allowed_statuses(self):
        from gdpr_utils import check_legitimate_interest
        for status in ["new", "scored", "approved", "outreach", "replied", "qualified"]:
            self.assertTrue(check_legitimate_interest(status), f"{status} should be allowed")

    def test_disallowed_statuses(self):
        from gdpr_utils import check_legitimate_interest
        for status in ["deleted", "archived", "unknown", ""]:
            self.assertFalse(check_legitimate_interest(status), f"{status} should be disallowed")


class TestRetentionCheck(unittest.TestCase):
    def test_recent_lead_not_expired(self):
        from gdpr_utils import is_past_retention
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.assertFalse(is_past_retention(now, None, False))

    def test_old_unconverted_lead_expired(self):
        from gdpr_utils import is_past_retention
        self.assertTrue(is_past_retention("2020-01-01T00:00:00+00:00", None, False))

    def test_old_converted_lead_with_long_retention(self):
        from gdpr_utils import is_past_retention
        # 200 days ago — past 90 day unconverted, but within 365 day converted
        from datetime import datetime, timezone, timedelta
        d = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        self.assertFalse(is_past_retention(d, None, True))

    def test_invalid_date_treated_as_expired(self):
        from gdpr_utils import is_past_retention
        self.assertTrue(is_past_retention("not-a-date", None, False))


if __name__ == "__main__":
    unittest.main()

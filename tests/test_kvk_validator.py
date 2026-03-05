"""
tests/test_kvk_validator.py — Unit tests for KvK validation.
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@patch.dict("os.environ", {"KVK_API_KEY": ""})
class TestKvKValidatorNoKey(unittest.TestCase):

    def test_search_without_api_key(self):
        from kvk_validator import search_kvk_by_name
        result = search_kvk_by_name("Test BV")
        self.assertEqual(result, [])

    def test_lookup_without_api_key(self):
        from kvk_validator import lookup_kvk_number
        result = lookup_kvk_number("12345678")
        self.assertIsNone(result)


@patch.dict("os.environ", {"KVK_API_KEY": "test-kvk-key"})
class TestKvKValidatorWithKey(unittest.TestCase):

    @patch("kvk_validator.httpx.Client")
    def test_search_returns_results(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "resultaten": [
                {
                    "kvkNummer": "12345678",
                    "handelsnaam": "Acme BV",
                    "adres": {"plaats": "Amsterdam"},
                    "actief": "Ja",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from kvk_validator import search_kvk_by_name
        with patch("kvk_validator.KVK_API_KEY", "test-kvk-key"):
            results = search_kvk_by_name("Acme BV")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["kvk_number"], "12345678")
        self.assertTrue(results[0]["is_active"])

    @patch("kvk_validator.httpx.Client")
    def test_search_404_returns_empty(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from kvk_validator import search_kvk_by_name
        results = search_kvk_by_name("Nonexistent BV")
        self.assertEqual(results, [])

    def test_invalid_kvk_number_format(self):
        from kvk_validator import lookup_kvk_number
        result = lookup_kvk_number("123")  # Too short
        self.assertIsNone(result)

        result = lookup_kvk_number("abcdefgh")  # Not digits
        self.assertIsNone(result)


class TestValidateLead(unittest.TestCase):

    @patch.dict("os.environ", {"KVK_API_KEY": ""})
    def test_fallback_validation_nl_domain(self):
        from kvk_validator import validate_lead
        result = validate_lead("Acme BV", website="https://acme.nl")
        self.assertTrue(result["validated"])
        self.assertEqual(result["confidence"], "medium")

    @patch.dict("os.environ", {"KVK_API_KEY": ""})
    def test_fallback_validation_spam_name(self):
        from kvk_validator import validate_lead
        result = validate_lead("test", website="https://test.nl")
        self.assertFalse(result["validated"])

    @patch.dict("os.environ", {"KVK_API_KEY": ""})
    def test_fallback_validation_short_name(self):
        from kvk_validator import validate_lead
        result = validate_lead("X")
        self.assertFalse(result["validated"])

    @patch.dict("os.environ", {"KVK_API_KEY": "test-key"})
    @patch("kvk_validator.search_kvk_by_name")
    def test_validate_with_kvk_match(self, mock_search):
        mock_search.return_value = [
            {
                "kvk_number": "12345678",
                "trade_name": "Acme BV",
                "city": "Amsterdam",
                "is_active": True,
            }
        ]
        from kvk_validator import validate_lead
        result = validate_lead("Acme BV", city="Amsterdam")
        self.assertTrue(result["validated"])
        self.assertEqual(result["kvk_number"], "12345678")

    @patch.dict("os.environ", {"KVK_API_KEY": "test-key"})
    @patch("kvk_validator.search_kvk_by_name")
    def test_validate_no_match(self, mock_search):
        mock_search.return_value = []
        from kvk_validator import validate_lead
        result = validate_lead("Nonexistent BV")
        # Falls back to heuristic
        self.assertEqual(result["confidence"], "low")


class TestMarkLeadValidated(unittest.TestCase):

    def test_updates_db(self):
        from kvk_validator import mark_lead_validated
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = cur

        mark_lead_validated(conn, "uuid-123", {"validated": True})
        conn.commit.assert_called_once()
        cur.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()

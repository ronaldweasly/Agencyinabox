"""
tests/test_lead_discovery.py — Unit tests for lead discovery module.

All external API calls are mocked — no live APIs required.
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _mock_conn(fetchone_return=None, fetchall_return=None):
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = fetchone_return
    cur.fetchall.return_value = fetchall_return or []
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


@patch.dict("os.environ", {
    "DOMAIN_PEPPER": "test-pepper-12345",
    "OUTSCRAPER_API_KEY": "",
    "APOLLO_API_KEY": "",
    "ANYMAIL_API_KEY": "",
})
class TestLeadDiscovery(unittest.TestCase):

    def test_scrape_google_maps_no_api_key(self):
        """Without OUTSCRAPER_API_KEY, should return empty list."""
        from lead_discovery import scrape_google_maps
        with patch("lead_discovery.OUTSCRAPER_API_KEY", ""):
            results = scrape_google_maps("IT consultant Amsterdam")
        self.assertEqual(results, [])

    @patch("lead_discovery.httpx.Client")
    def test_scrape_google_maps_with_results(self, mock_client_cls):
        """With API key and mocked response, should parse leads."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [[
                {
                    "name": "Tech BV",
                    "site": "https://tech-bv.nl",
                    "phone": "+31612345678",
                    "city": "Amsterdam",
                    "category": "IT",
                },
                {
                    "name": "No Website Co",
                    "site": "",
                },
            ]]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from lead_discovery import scrape_google_maps
        with patch("lead_discovery.OUTSCRAPER_API_KEY", "test-key"):
            results = scrape_google_maps("IT consultant Amsterdam")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company_name, "Tech BV")
        self.assertEqual(results[0].domain, "tech-bv.nl")
        self.assertEqual(len(results[0].domain_hash), 64)

    def test_enrich_lead_no_keys(self):
        """Without API keys, enrichment should be graceful no-op."""
        from lead_discovery import enrich_lead, RawLead
        lead = RawLead(
            company_name="Test BV",
            website="https://test.nl",
            domain="test.nl",
            domain_hash="a" * 64,
        )
        result = enrich_lead(lead)
        self.assertIsNone(result.contact_email)

    def test_store_leads_dedup(self):
        """Second insert with same domain_hash should be skipped."""
        from lead_discovery import store_leads, RawLead

        conn, cur = _mock_conn()
        # First call returns id (inserted), second returns None (duplicate)
        cur.fetchone.side_effect = [("uuid-1",), None]

        leads = [
            RawLead(
                company_name="A", website="a.nl", domain="a.nl",
                domain_hash="hash_a", contact_email="a@a.nl",
            ),
            RawLead(
                company_name="B", website="b.nl", domain="b.nl",
                domain_hash="hash_b", contact_email="b@b.nl",
            ),
        ]

        inserted, skipped = store_leads(conn, leads)
        self.assertEqual(inserted, 1)
        self.assertEqual(skipped, 1)

    def test_run_discovery_empty_queries(self):
        """Empty query list should return empty."""
        from lead_discovery import run_discovery
        conn, _ = _mock_conn()
        result = run_discovery(conn, [])
        self.assertEqual(result, [])


@patch.dict("os.environ", {
    "DOMAIN_PEPPER": "test-pepper-12345",
    "APOLLO_API_KEY": "test-apollo-key",
})
class TestApolloEnrichment(unittest.TestCase):

    @patch("lead_discovery.httpx.Client")
    def test_apollo_returns_contact(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "people": [{
                "email": "ceo@acme.nl",
                "name": "Jan de Boer",
                "title": "CEO",
                "organization": {"name": "Acme BV"},
            }]
        }
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from lead_discovery import enrich_with_apollo
        with patch("lead_discovery.APOLLO_API_KEY", "test-apollo-key"):
            result = enrich_with_apollo("acme.nl")
        self.assertEqual(result["contact_email"], "ceo@acme.nl")
        self.assertEqual(result["contact_name"], "Jan de Boer")


if __name__ == "__main__":
    unittest.main()

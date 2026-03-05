"""
tests/test_lead_scorer.py — Unit tests for ICP lead scoring.
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

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
    "GEMINI_API_KEY": "test-gemini-key",
    "DOMAIN_PEPPER": "test-pepper",
    "DATABASE_URL": "postgresql://fake/db",
    "ANTHROPIC_API_KEY": "test",
    "TELEGRAM_BOT_TOKEN": "test",
    "TELEGRAM_CHAT_ID": "test",
    "TELEGRAM_WEBHOOK_SECRET": "test",
    "GITHUB_PAT": "test",
    "GITHUB_ORG": "test",
    "FLY_API_TOKEN": "test",
})
class TestICPScore(unittest.TestCase):

    def test_icp_score_model_valid(self):
        from lead_scorer import ICPScore
        score = ICPScore(
            score=85,
            reasoning="Good fit for IT consulting niche",
            niche_match=True,
            has_decision_maker=True,
            dutch_entity=True,
            red_flags=[],
            recommended_action="approve",
        )
        self.assertEqual(score.score, 85)
        self.assertTrue(score.niche_match)

    def test_icp_score_bounds(self):
        from lead_scorer import ICPScore
        # Below 0
        with self.assertRaises(Exception):
            ICPScore(
                score=-1, reasoning="", niche_match=False,
                has_decision_maker=False, dutch_entity=False,
                recommended_action="reject",
            )
        # Above 100
        with self.assertRaises(Exception):
            ICPScore(
                score=101, reasoning="", niche_match=False,
                has_decision_maker=False, dutch_entity=False,
                recommended_action="reject",
            )

    @patch("lead_scorer.gemini_client")
    def test_score_lead_calls_gemini(self, mock_gemini):
        from lead_scorer import score_lead, ICPScore

        mock_gemini.chat.completions.create.return_value = ICPScore(
            score=75,
            reasoning="Matches IT consulting niche",
            niche_match=True,
            has_decision_maker=True,
            dutch_entity=True,
            red_flags=[],
            recommended_action="approve",
        )

        lead = {
            "company_name": "Tech BV",
            "website": "https://tech.nl",
            "contact_email": "info@tech.nl",
            "kvk_validated": True,
        }
        result = score_lead(lead)
        self.assertEqual(result.score, 75)
        self.assertEqual(result.recommended_action, "approve")
        mock_gemini.chat.completions.create.assert_called_once()

    @patch("lead_scorer.gemini_client")
    def test_score_leads_batch_updates_db(self, mock_gemini):
        from lead_scorer import score_leads_batch, ICPScore

        mock_gemini.chat.completions.create.return_value = ICPScore(
            score=60,
            reasoning="Decent fit",
            niche_match=True,
            has_decision_maker=False,
            dutch_entity=True,
            red_flags=["no_decision_maker"],
            recommended_action="review",
        )

        conn, cur = _mock_conn(
            fetchone_return=("uuid-1", "Acme BV", "acme.nl", "info@acme.nl", None, False)
        )

        results = score_leads_batch(conn, ["uuid-1"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["score"], 60)
        # Should update DB
        self.assertTrue(conn.commit.called)

    @patch("lead_scorer.gemini_client")
    def test_score_leads_batch_missing_lead(self, mock_gemini):
        conn, cur = _mock_conn(fetchone_return=None)

        from lead_scorer import score_leads_batch
        results = score_leads_batch(conn, ["nonexistent-uuid"])
        self.assertEqual(len(results), 0)


class TestDefaultICP(unittest.TestCase):

    def test_default_icp_has_required_keys(self):
        from lead_scorer import DEFAULT_ICP
        self.assertIn("target_niches", DEFAULT_ICP)
        self.assertIn("target_regions", DEFAULT_ICP)
        self.assertIn("disqualifiers", DEFAULT_ICP)
        self.assertIsInstance(DEFAULT_ICP["target_niches"], list)


if __name__ == "__main__":
    unittest.main()

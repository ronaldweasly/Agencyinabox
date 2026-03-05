"""
tests/test_instantly_client.py — Unit tests for Instantly.ai integration.
"""
from __future__ import annotations

import sys
import os
import json
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


@patch.dict("os.environ", {"INSTANTLY_API_KEY": ""})
class TestInstantlyNoKey(unittest.TestCase):

    def test_list_campaigns_no_key(self):
        from instantly_client import list_campaigns
        result = list_campaigns()
        self.assertEqual(result, [])

    def test_add_lead_no_key(self):
        from instantly_client import add_lead_to_campaign
        result = add_lead_to_campaign("camp-1", "test@test.nl")
        self.assertFalse(result)

    def test_send_outreach_no_key(self):
        from instantly_client import send_outreach
        conn, _ = _mock_conn()
        result = send_outreach(conn, "lead-1", "camp-1")
        self.assertFalse(result)


@patch.dict("os.environ", {"INSTANTLY_API_KEY": "test-key"})
class TestInstantlyWithKey(unittest.TestCase):

    @patch("instantly_client.httpx.Client")
    def test_add_lead_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from instantly_client import add_lead_to_campaign
        with patch("instantly_client.INSTANTLY_API_KEY", "test-key"):
            result = add_lead_to_campaign("camp-1", "jan@acme.nl", "Jan", "Boer", "Acme BV")
        self.assertTrue(result)

    @patch("instantly_client.httpx.Client")
    def test_add_lead_failure(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from instantly_client import add_lead_to_campaign
        with patch("instantly_client.INSTANTLY_API_KEY", "test-key"):
            result = add_lead_to_campaign("camp-1", "jan@acme.nl")
        self.assertFalse(result)

    @patch("instantly_client.httpx.Client")
    def test_add_leads_batch(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"leads_added": 3}
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        from instantly_client import add_leads_batch
        leads = [
            {"email": "a@a.nl", "first_name": "A", "company_name": "A BV"},
            {"email": "b@b.nl", "first_name": "B", "company_name": "B BV"},
            {"email": "c@c.nl", "first_name": "C", "company_name": "C BV"},
        ]
        with patch("instantly_client.INSTANTLY_API_KEY", "test-key"):
            count = add_leads_batch("camp-1", leads)
        self.assertEqual(count, 3)

    def test_add_leads_batch_empty(self):
        from instantly_client import add_leads_batch
        count = add_leads_batch("camp-1", [])
        self.assertEqual(count, 0)


class TestProcessReplyWebhook(unittest.TestCase):

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test-key"})
    def test_process_reply_creates_job(self):
        from instantly_client import process_reply_webhook

        conn, cur = _mock_conn()
        # First call: lead lookup, second call: job insert
        cur.fetchone.side_effect = [
            ("lead-uuid-1", "approved"),  # lead lookup
            ("job-uuid-1",),  # job insert
        ]

        webhook = {
            "event_type": "reply_received",
            "email": "jan@acme.nl",
            "message_body": "Interessant! Vertel meer.",
            "campaign_id": "camp-1",
        }

        job_id = process_reply_webhook(conn, webhook)
        self.assertEqual(job_id, "job-uuid-1")

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test-key"})
    def test_process_non_reply_event(self):
        from instantly_client import process_reply_webhook
        conn, _ = _mock_conn()

        webhook = {
            "event_type": "email_sent",
            "email": "jan@acme.nl",
        }

        result = process_reply_webhook(conn, webhook)
        self.assertIsNone(result)

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test-key"})
    def test_process_reply_unknown_lead(self):
        from instantly_client import process_reply_webhook
        conn, cur = _mock_conn(fetchone_return=None)

        webhook = {
            "event_type": "reply_received",
            "email": "unknown@unknown.nl",
            "message_body": "Hello!",
        }

        result = process_reply_webhook(conn, webhook)
        self.assertIsNone(result)


class TestSendOutreach(unittest.TestCase):

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test-key"})
    @patch("instantly_client.add_lead_to_campaign")
    def test_send_outreach_success(self, mock_add):
        mock_add.return_value = True
        from instantly_client import send_outreach

        conn, cur = _mock_conn(
            fetchone_return=("lead-1", "Acme BV", "jan@acme.nl", "Jan de Boer")
        )

        with patch("instantly_client.INSTANTLY_API_KEY", "test-key"):
            result = send_outreach(conn, "lead-1", "camp-1")
        self.assertTrue(result)
        mock_add.assert_called_once()
        conn.commit.assert_called()

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test-key"})
    def test_send_outreach_no_email(self):
        from instantly_client import send_outreach

        conn, cur = _mock_conn(
            fetchone_return=("lead-1", "Acme BV", None, "Jan")  # No email
        )

        with patch("instantly_client.INSTANTLY_API_KEY", "test-key"):
            result = send_outreach(conn, "lead-1", "camp-1")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()

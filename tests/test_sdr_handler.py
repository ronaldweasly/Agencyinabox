"""
tests/test_sdr_handler.py — Unit tests for SDR reply handler.
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

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
class TestDraftReply(unittest.TestCase):

    def test_draft_reply_model(self):
        from sdr_handler import DraftReply
        reply = DraftReply(
            reply_text="Beste Jan, bedankt voor uw reactie.",
            conversation_stage="interest",
            sentiment="positive",
            confidence=85,
            suggested_action="send",
            key_points=["Shows interest in automation"],
        )
        self.assertEqual(reply.conversation_stage, "interest")
        self.assertEqual(reply.confidence, 85)

    def test_draft_reply_confidence_bounds(self):
        from sdr_handler import DraftReply
        with self.assertRaises(Exception):
            DraftReply(
                reply_text="Test", conversation_stage="interest",
                sentiment="positive", confidence=-1,
                suggested_action="send",
            )
        with self.assertRaises(Exception):
            DraftReply(
                reply_text="Test", conversation_stage="interest",
                sentiment="positive", confidence=101,
                suggested_action="send",
            )


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
class TestReplyLock(unittest.TestCase):

    @patch("sdr_handler.WORKER_ID", "test-worker-1")
    def test_acquire_lock_success(self):
        from sdr_handler import acquire_reply_lock
        conn, cur = _mock_conn(fetchone_return=("uuid-1",))
        result = acquire_reply_lock(conn, "uuid-1")
        self.assertTrue(result)
        conn.commit.assert_called()

    @patch("sdr_handler.WORKER_ID", "test-worker-1")
    def test_acquire_lock_already_held(self):
        from sdr_handler import acquire_reply_lock
        conn, cur = _mock_conn(fetchone_return=None)  # FOR UPDATE SKIP LOCKED finds nothing
        result = acquire_reply_lock(conn, "uuid-1")
        self.assertFalse(result)

    @patch("sdr_handler.WORKER_ID", "test-worker-1")
    def test_release_lock(self):
        from sdr_handler import release_reply_lock
        conn, cur = _mock_conn()
        release_reply_lock(conn, "uuid-1")
        conn.commit.assert_called_once()
        cur.execute.assert_called_once()


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
class TestConversationHistory(unittest.TestCase):

    def test_get_history_returns_chronological(self):
        from sdr_handler import get_conversation_history
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        conn, cur = _mock_conn(
            fetchall_return=[
                ("outbound", "Hi there!", now),
                ("inbound", "Hello!", now),
            ]
        )
        history = get_conversation_history(conn, "uuid-1")
        self.assertEqual(len(history), 2)
        # Should be reversed (chronological)
        self.assertEqual(history[0]["direction"], "inbound")
        self.assertEqual(history[1]["direction"], "outbound")


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
class TestStoreReply(unittest.TestCase):

    def test_store_inbound(self):
        from sdr_handler import store_reply
        conn, cur = _mock_conn(fetchone_return=("msg-uuid-1",))
        result = store_reply(conn, "lead-1", "inbound", "Hello!")
        self.assertEqual(result, "msg-uuid-1")
        conn.commit.assert_called_once()

    def test_store_outbound_pending(self):
        from sdr_handler import store_reply
        conn, cur = _mock_conn(fetchone_return=("msg-uuid-2",))
        result = store_reply(conn, "lead-1", "outbound", "Our reply")
        self.assertEqual(result, "msg-uuid-2")

    def test_store_failure_returns_none(self):
        from sdr_handler import store_reply
        conn, cur = _mock_conn()
        conn.cursor.side_effect = Exception("DB error")
        result = store_reply(conn, "lead-1", "inbound", "Hello!")
        self.assertIsNone(result)


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
class TestRunSdrReply(unittest.TestCase):

    def test_missing_lead_id(self):
        from sdr_handler import run_sdr_reply
        conn, _ = _mock_conn()
        job = {"id": "job-1", "payload": {"their_reply": "Hello!"}}
        cost = run_sdr_reply(conn, job)
        self.assertEqual(cost, 0.0)

    def test_missing_their_reply(self):
        from sdr_handler import run_sdr_reply
        conn, _ = _mock_conn()
        job = {"id": "job-1", "payload": {"lead_id": "lead-1"}}
        cost = run_sdr_reply(conn, job)
        self.assertEqual(cost, 0.0)


if __name__ == "__main__":
    unittest.main()

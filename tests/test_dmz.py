"""
tests/test_dmz.py — Unit tests for dmz/main.py (FastAPI webhook handler)

Uses FastAPI TestClient and mocks all external calls:
  - psycopg2.connect (database)
  - httpx.AsyncClient (GitHub API and Telegram API)
No live API keys or database required.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _get_client():
    """Import app after patching env vars so module-level os.environ reads succeed."""
    return TestClient(__import__("dmz.main", fromlist=["app"]).app)


VALID_SECRET = "test-webhook-secret"
AUTH_HEADERS = {"X-Telegram-Bot-Api-Secret-Token": VALID_SECRET}


class TestWebhookAuth(unittest.TestCase):

    def setUp(self):
        self.env = patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "123:FAKE",
                "GITHUB_PAT": "ghp_fake",
                "GITHUB_ORG": "test-org",
                "DATABASE_URL": "postgresql://fake/db",
                "TELEGRAM_WEBHOOK_SECRET": VALID_SECRET,
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_missing_secret_returns_403(self):
        """Request without auth header is rejected with 403."""
        from dmz.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/internal/telegram/callback",
            json={"callback_query": {"data": "APPROVE_PR:repo:1", "id": "cid"}},
        )
        self.assertEqual(resp.status_code, 403)

    def test_wrong_secret_returns_403(self):
        """Request with wrong secret is rejected with 403."""
        from dmz.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/internal/telegram/callback",
            json={"callback_query": {"data": "APPROVE_PR:repo:1", "id": "cid"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_unknown_callback_returns_ok(self):
        """Unknown callback data with valid auth returns {ok: True}."""
        from dmz.main import app, answer_callback
        client = TestClient(app, raise_server_exceptions=False)

        with patch("dmz.main.answer_callback", new=AsyncMock(return_value=None)):
            resp = client.post(
                "/internal/telegram/callback",
                json={"callback_query": {"data": "UNKNOWN_ACTION", "id": "cid"}},
                headers=AUTH_HEADERS,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("ok"))


class TestApprovePR(unittest.TestCase):

    def setUp(self):
        self.env = patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "123:FAKE",
                "GITHUB_PAT": "ghp_fake",
                "GITHUB_ORG": "test-org",
                "DATABASE_URL": "postgresql://fake/db",
                "TELEGRAM_WEBHOOK_SECRET": VALID_SECRET,
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_approve_already_merged_pr(self):
        """PR already merged — returns already_merged without calling merge."""
        from dmz.main import app
        client = TestClient(app, raise_server_exceptions=False)

        mock_pr_response = MagicMock()
        mock_pr_response.status_code = 200
        mock_pr_response.json.return_value = {
            "state": "closed", "merged": True
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_pr_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("dmz.main.answer_callback", new=AsyncMock(return_value=None)):
            resp = client.post(
                "/internal/telegram/callback",
                json={
                    "callback_query": {
                        "data": "APPROVE_PR:my-repo:42",
                        "id": "cid",
                    }
                },
                headers=AUTH_HEADERS,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "already_merged")

    def test_malformed_approve_returns_400(self):
        """APPROVE_PR with wrong number of parts returns 400."""
        from dmz.main import app
        client = TestClient(app, raise_server_exceptions=False)

        with patch("dmz.main.answer_callback", new=AsyncMock(return_value=None)):
            resp = client.post(
                "/internal/telegram/callback",
                json={
                    "callback_query": {
                        "data": "APPROVE_PR:only-one-part",
                        "id": "cid",
                    }
                },
                headers=AUTH_HEADERS,
            )
        self.assertEqual(resp.status_code, 400)


class TestRejectPR(unittest.TestCase):

    def setUp(self):
        self.env = patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "123:FAKE",
                "GITHUB_PAT": "ghp_fake",
                "GITHUB_ORG": "test-org",
                "DATABASE_URL": "postgresql://fake/db",
                "TELEGRAM_WEBHOOK_SECRET": VALID_SECRET,
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_reject_pr_requeues_job(self):
        """REJECT_PR closes PR and updates job to pending."""
        from dmz.main import app
        client = TestClient(app, raise_server_exceptions=False)

        mock_patch_response = MagicMock()
        mock_patch_response.status_code = 200

        mock_http_client = AsyncMock()
        mock_http_client.patch = AsyncMock(return_value=mock_patch_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        mock_db_conn = MagicMock()
        mock_db_cur = MagicMock()
        mock_db_cur.__enter__ = lambda s: s
        mock_db_cur.__exit__ = MagicMock(return_value=False)
        mock_db_conn.cursor.return_value = mock_db_cur
        mock_db_conn.__enter__ = lambda s: s
        mock_db_conn.__exit__ = MagicMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_http_client), \
             patch("psycopg2.connect", return_value=mock_db_conn), \
             patch("dmz.main.answer_callback", new=AsyncMock(return_value=None)):
            resp = client.post(
                "/internal/telegram/callback",
                json={
                    "callback_query": {
                        "data": "REJECT_PR:my-repo:42:job-uuid-1234",
                        "id": "cid",
                    }
                },
                headers=AUTH_HEADERS,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "re_queued")


class TestHealthCheck(unittest.TestCase):

    def test_health_endpoint(self):
        """GET /health returns ok."""
        self.env = patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "123:FAKE",
                "GITHUB_PAT": "ghp_fake",
                "GITHUB_ORG": "test-org",
                "DATABASE_URL": "postgresql://fake/db",
                "TELEGRAM_WEBHOOK_SECRET": VALID_SECRET,
            },
        )
        self.env.start()

        from dmz.main import app
        client = TestClient(app)
        resp = client.get("/health")

        self.env.stop()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()

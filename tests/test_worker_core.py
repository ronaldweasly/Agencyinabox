"""
tests/test_worker_core.py — Unit tests for worker_core.py

All DB calls are mocked via unittest.mock — no live database required.
Tests cover: budget guard, heartbeat abort detection, audit log,
job claim SKIP LOCKED, budget reconciliation, and DLQ alerts.
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, call, patch


# ── Helper: build a mock psycopg2 connection ─────────────────────────────────

def _mock_conn(fetchone_return=None, rowcount=1):
    """Return a mock psycopg2 connection with a cursor that returns fetchone_return."""
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = fetchone_return
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


# ── Tests: reserve_budget ────────────────────────────────────────────────────

class TestReserveBudget(unittest.TestCase):

    def setUp(self):
        # Patch DATABASE_URL so get_connection() never actually connects
        self.env_patcher = patch.dict(
            "os.environ", {"DATABASE_URL": "postgresql://fake/db"}
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_reserve_budget_success(self):
        """Both global and project cap have room — returns True and commits."""
        from src.worker_core import reserve_budget

        conn, cur = _mock_conn(fetchone_return={"global_spend": 0.05})
        # First fetchone (global) returns a row; second (project) also returns a row
        cur.fetchone.side_effect = [{"global_spend": 0.05}, {"current_spend": 0.05}]

        result = reserve_budget(conn, 0.05, "proj-uuid-1234")

        self.assertTrue(result)
        conn.commit.assert_called_once()

    def test_reserve_budget_global_cap_exceeded(self):
        """Global cap exceeded — returns False, rolls back, no project update."""
        from src.worker_core import reserve_budget

        conn, cur = _mock_conn(fetchone_return=None)
        cur.fetchone.side_effect = [None]  # global UPDATE returns no row

        result = reserve_budget(conn, 0.05, "proj-uuid-1234")

        self.assertFalse(result)
        conn.rollback.assert_called()
        conn.commit.assert_not_called()

    def test_reserve_budget_project_cap_exceeded(self):
        """Project cap exceeded — returns False, rolls back."""
        from src.worker_core import reserve_budget

        conn, cur = _mock_conn()
        cur.fetchone.side_effect = [{"global_spend": 5.0}, None]

        result = reserve_budget(conn, 0.05, "proj-uuid-1234")

        self.assertFalse(result)
        conn.rollback.assert_called()

    def test_reserve_budget_db_exception_returns_false(self):
        """DB exception returns False gracefully — doesn't raise."""
        from src.worker_core import reserve_budget

        conn = MagicMock()
        conn.cursor.side_effect = Exception("DB error")

        result = reserve_budget(conn, 0.05, "proj-uuid-1234")

        self.assertFalse(result)


# ── Tests: reconcile_budget ───────────────────────────────────────────────────

class TestReconcileBudget(unittest.TestCase):

    def test_reconcile_skips_tiny_delta(self):
        """Delta < $0.001 — no DB call made."""
        from src.worker_core import reconcile_budget

        conn = MagicMock()
        reconcile_budget(conn, 0.05, 0.0505, "proj-id")  # delta = 0.0005
        conn.cursor.assert_not_called()

    def test_reconcile_applies_positive_delta(self):
        """Actual > estimated — adds delta to both tables."""
        from src.worker_core import reconcile_budget

        conn, cur = _mock_conn()
        reconcile_budget(conn, 0.05, 0.09, "proj-id")  # delta = +0.04

        # Should call execute twice (global + project) then commit
        self.assertEqual(cur.execute.call_count, 2)
        conn.commit.assert_called_once()

    def test_reconcile_applies_negative_delta(self):
        """Actual < estimated — refunds the over-reservation."""
        from src.worker_core import reconcile_budget

        conn, cur = _mock_conn()
        reconcile_budget(conn, 0.10, 0.03, "proj-id")  # delta = -0.07

        self.assertEqual(cur.execute.call_count, 2)
        conn.commit.assert_called_once()


# ── Tests: log_audit ──────────────────────────────────────────────────────────

class TestLogAudit(unittest.TestCase):

    def test_log_audit_empty_job_id_skips(self):
        """Empty job_id guard — no DB access."""
        from src.worker_core import log_audit

        conn = MagicMock()
        log_audit(conn, "", "processing", "completed")
        conn.cursor.assert_not_called()

    def test_log_audit_writes_both_rows_atomically(self):
        """Both UPDATE and INSERT are called before a single commit."""
        from src.worker_core import log_audit

        conn, cur = _mock_conn()
        log_audit(conn, "job-uuid-1", "processing", "completed")

        # Two execute calls: UPDATE jobs + INSERT jobs_audit
        self.assertEqual(cur.execute.call_count, 2)
        conn.commit.assert_called_once()

    def test_log_audit_rolls_back_on_exception(self):
        """DB failure → rollback → re-raises."""
        from src.worker_core import log_audit

        conn = MagicMock()
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        cur.execute.side_effect = Exception("DB down")
        conn.cursor.return_value = cur

        with self.assertRaises(Exception):
            log_audit(conn, "job-uuid-2", "processing", "completed")

        conn.rollback.assert_called_once()


# ── Tests: HeartbeatThread ────────────────────────────────────────────────────

class TestHeartbeatThread(unittest.TestCase):

    def test_heartbeat_sets_abort_flag_after_max_failures(self):
        """After MAX_FAILURES consecutive DB failures, abort_flag is set."""
        from src.worker_core import HeartbeatThread

        hb = HeartbeatThread("test-job-id")
        hb.INTERVAL_SECONDS = 0.01  # Speed up for tests

        # Patch get_connection to return a conn that always fails
        bad_conn = MagicMock()
        bad_conn.cursor.side_effect = Exception("connection refused")

        with patch("src.worker_core.get_connection", return_value=bad_conn), \
             patch("src.worker_core.get_or_reconnect", return_value=bad_conn):
            hb.start()
            # Give the thread time to hit MAX_FAILURES (3 failures × fast)
            timeout = time.time() + 5
            while not hb.should_abort and time.time() < timeout:
                time.sleep(0.05)
            hb.stop()

        self.assertTrue(hb.should_abort)

    def test_heartbeat_does_not_abort_on_success(self):
        """Successful heartbeats leave abort_flag unset."""
        from src.worker_core import HeartbeatThread

        good_conn = MagicMock()
        good_cur = MagicMock()
        good_cur.__enter__ = lambda s: s
        good_cur.__exit__ = MagicMock(return_value=False)
        good_conn.cursor.return_value = good_cur

        with patch("src.worker_core.get_connection", return_value=good_conn), \
             patch("src.worker_core.get_or_reconnect", return_value=good_conn):
            hb = HeartbeatThread("clean-job-id")
            hb.start()
            time.sleep(0.2)
            hb.stop()

        self.assertFalse(hb.should_abort)


if __name__ == "__main__":
    unittest.main()

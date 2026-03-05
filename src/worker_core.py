"""
worker_core.py — Job queue consumer with heartbeat, budget guard, and audit log.

Fixes applied from PROBLEMS.md:
  P-05: Heartbeat uses its OWN dedicated connection (not shared with main thread).
  P-06: Connection health check + automatic reconnection.
  P-07: Heartbeat failure sets abort flag; main thread checks it.
  P-08: Actual cost reconciled against estimated cost after success.
  P-09: Both budget UPDATEs in single explicit transaction (already implicit, now documented).
  P-10: ensure_daily_spend() called before budget check.
  P-25: execute_job() interface defined with clear contract.
  Bug #1:  conn.commit() after budget guard.
  Bug #2:  job existence checked before log_audit.
  Bug #3:  Audit log uses single atomic transaction.
  Bug #4:  Budget refunded on LLM call failure.
  Bug #5:  Watchdog has audit trail (in SQL, not here).
  Bug #11: Heartbeat thread implemented with failure detection.
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from config import WORKER_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ── Shutdown coordination ────────────────────────────────────────────────────

SHUTDOWN_FLAG = threading.Event()


def handle_sigterm(signum: int, frame: Any) -> None:
    log.info(f"[{WORKER_ID}] SIGTERM received. Finishing current job then exiting.")
    SHUTDOWN_FLAG.set()


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


# ── Connection management (P-06 fix) ────────────────────────────────────────

def get_connection() -> psycopg2.extensions.connection:
    """Create a new Postgres connection from Doppler-injected env var."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False  # Explicit transaction control
    return conn


def check_connection(conn: psycopg2.extensions.connection) -> bool:
    """Return True if the connection is alive."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()  # Don't leave an idle-in-transaction
        return True
    except Exception:
        return False


def get_or_reconnect(conn: psycopg2.extensions.connection | None) -> psycopg2.extensions.connection:
    """Return existing connection if healthy, or create a new one (P-06)."""
    if conn is not None and check_connection(conn):
        return conn
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        log.warning(f"[{WORKER_ID}] Connection lost. Reconnecting...")
    return get_connection()


# ── Heartbeat (P-05: own connection; P-07: abort flag on failure) ────────────

class HeartbeatThread:
    """
    Updates job.updated_at every 30s to prevent watchdog false-positive reclaim.

    P-05 fix: Uses its OWN psycopg2 connection, never shares with main thread.
    P-07 fix: Sets abort_flag after MAX_FAILURES consecutive failures so the
              main thread can detect heartbeat death and stop processing.
    """

    MAX_FAILURES = 3
    INTERVAL_SECONDS = 30

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.stop_event = threading.Event()
        self.abort_flag = threading.Event()  # P-07: main thread checks this
        self._thread: threading.Thread | None = None
        self._conn: psycopg2.extensions.connection | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"heartbeat-{self.job_id[:8]}"
        )
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass

    @property
    def should_abort(self) -> bool:
        """Main thread calls this to check if heartbeat has fatally failed."""
        return self.abort_flag.is_set()

    def _run(self) -> None:
        consecutive_failures = 0
        self._conn = get_connection()  # P-05: dedicated connection

        while not self.stop_event.is_set():
            try:
                self._conn = get_or_reconnect(self._conn)
                with self._conn.cursor() as cur:
                    cur.execute(
                        "UPDATE jobs SET updated_at = NOW() WHERE id = %s",
                        (self.job_id,),
                    )
                self._conn.commit()
                consecutive_failures = 0
            except Exception as e:
                log.warning(f"Heartbeat failed for job {self.job_id}: {e}")
                consecutive_failures += 1
                if consecutive_failures >= self.MAX_FAILURES:
                    log.error(
                        f"Heartbeat dead for job {self.job_id} after "
                        f"{self.MAX_FAILURES} failures. Setting abort flag."
                    )
                    self.abort_flag.set()  # P-07: signal main thread
                    return  # Stop the heartbeat thread

            self.stop_event.wait(timeout=self.INTERVAL_SECONDS)


# ── Audit log (Bug #3 fix: atomic transaction) ──────────────────────────────

def log_audit(
    conn: psycopg2.extensions.connection,
    job_id: str,
    old_status: str,
    new_status: str,
    error_msg: str | None = None,
) -> None:
    """
    Atomically updates job status AND writes audit row in one transaction.
    Bug #3 fix: Both writes commit together — either both succeed or both rollback.
    Bug #2 fix: Caller must verify job_id is not None before calling.
    """
    if not job_id:
        log.error("log_audit called with empty job_id — skipping (Bug #2 guard)")
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = %s, updated_at = NOW() WHERE id = %s",
                (new_status, job_id),
            )
            cur.execute(
                """INSERT INTO jobs_audit
                   (job_id, old_status, new_status, worker_id, error_message)
                   VALUES (%s, %s, %s, %s, %s)""",
                (job_id, old_status, new_status, WORKER_ID, error_msg),
            )
        conn.commit()  # Bug #3: single atomic commit
    except Exception as e:
        conn.rollback()
        log.error(f"Audit log failed for job {job_id}: {e}")
        raise


# ── Budget guard (P-08, P-09, P-10, Bug #1, Bug #4) ────────────────────────

def reserve_budget(
    conn: psycopg2.extensions.connection,
    estimated_cost: float,
    project_id: str,
) -> bool:
    """
    Atomically checks and reserves budget against both global daily cap
    and per-project cap. Returns False if either would be exceeded.

    P-10 fix: Calls ensure_daily_spend() to guarantee today's row exists.
    P-09 fix: Both UPDATEs are in the same implicit transaction.
    Bug #1 fix: conn.commit() called on success.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # P-10 fix: ensure today's row exists before UPDATE
            cur.execute("SELECT ensure_daily_spend()")

            # Global daily cap — atomic check + increment
            cur.execute(
                """UPDATE daily_spend
                   SET global_spend = global_spend + %s
                   WHERE date = CURRENT_DATE
                     AND global_spend + %s <= global_cap
                   RETURNING global_spend""",
                (estimated_cost, estimated_cost),
            )
            if not cur.fetchone():
                conn.rollback()
                log.warning("Global daily budget cap reached. Job deferred.")
                return False

            # Per-project cap — atomic check + increment
            # P-24 fix: resolve budget_id through projects table
            cur.execute(
                """UPDATE project_budgets pb
                   SET current_spend = pb.current_spend + %s
                   FROM projects p
                   WHERE p.budget_id = pb.project_id
                     AND p.id = %s
                     AND pb.current_spend + %s <= pb.project_cap
                   RETURNING pb.current_spend""",
                (estimated_cost, project_id, estimated_cost),
            )
            if not cur.fetchone():
                conn.rollback()  # Rolls back global increment too (same txn, P-09)
                log.warning(f"Project budget cap reached for {project_id}.")
                return False

        conn.commit()  # Bug #1: persist budget reservation immediately
        return True

    except Exception as e:
        conn.rollback()
        log.error(f"Budget reservation failed: {e}")
        return False


def release_budget(
    conn: psycopg2.extensions.connection,
    cost: float,
    project_id: str,
) -> None:
    """Refund budget on API call failure (Bug #4 fix)."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE daily_spend
                   SET global_spend = GREATEST(0, global_spend - %s)
                   WHERE date = CURRENT_DATE""",
                (cost,),
            )
            cur.execute(
                """UPDATE project_budgets pb
                   SET current_spend = GREATEST(0, pb.current_spend - %s)
                   FROM projects p
                   WHERE p.budget_id = pb.project_id
                     AND p.id = %s""",
                (cost, project_id),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Budget release failed for project {project_id}: {e}")


def reconcile_budget(
    conn: psycopg2.extensions.connection,
    estimated_cost: float,
    actual_cost: float,
    project_id: str,
) -> None:
    """
    P-08 fix: After successful execution, adjust budget to reflect actual
    cost instead of the pre-estimated cost.

    delta > 0 means we under-estimated → need to reserve more.
    delta < 0 means we over-estimated → need to refund the difference.
    """
    delta = actual_cost - estimated_cost
    if abs(delta) < 0.001:
        return  # Close enough, skip the DB round-trip

    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE daily_spend
                   SET global_spend = GREATEST(0, global_spend + %s)
                   WHERE date = CURRENT_DATE""",
                (delta,),
            )
            cur.execute(
                """UPDATE project_budgets pb
                   SET current_spend = GREATEST(0, pb.current_spend + %s)
                   FROM projects p
                   WHERE p.budget_id = pb.project_id
                     AND p.id = %s""",
                (delta, project_id),
            )
        conn.commit()
        if delta > 0:
            log.info(
                f"Budget reconciled: +${delta:.4f} for project {project_id} "
                f"(estimated ${estimated_cost:.4f}, actual ${actual_cost:.4f})"
            )
    except Exception as e:
        conn.rollback()
        log.error(f"Budget reconciliation failed: {e}")


# ── Job claim (SKIP LOCKED) ─────────────────────────────────────────────────

def claim_job(conn: psycopg2.extensions.connection) -> dict | None:
    """
    Atomically claim one pending job. Commits immediately to release the
    advisory lock (lock held < 50ms).
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = 'processing', worker_id = %s, updated_at = NOW()
                   WHERE id = (
                       SELECT id FROM jobs
                       WHERE status = 'pending'
                       ORDER BY created_at ASC
                       FOR UPDATE SKIP LOCKED
                       LIMIT 1
                   )
                   RETURNING id, project_id, job_type, payload,
                             retry_count, max_retries""",
                (WORKER_ID,),
            )
            job = cur.fetchone()
        conn.commit()  # Release lock immediately
        return dict(job) if job else None
    except Exception as e:
        conn.rollback()
        log.error(f"Job claim failed: {e}")
        return None


# ── DLQ alert ────────────────────────────────────────────────────────────────

def send_dlq_alert(
    conn: psycopg2.extensions.connection,
    job_id: str,
    error: str,
) -> None:
    """Insert a DLQ alert row. Telegram bot polls this table."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO alerts (alert_type, message, job_id)
                   VALUES ('DLQ', %s, %s)""",
                (f"Job {job_id} exhausted retries: {error[:500]}", job_id),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to insert DLQ alert for {job_id}: {e}")


# ── P-25 fix: execute_job interface ──────────────────────────────────────────

def execute_job(
    conn: psycopg2.extensions.connection,
    job: dict,
    heartbeat: HeartbeatThread,
) -> float:
    """
    Route a job to the correct executor based on job_type.

    Returns:
        float: The actual API cost incurred (in USD).

    Raises:
        Exception: On any failure (budget will be refunded by caller).

    The heartbeat's abort flag is checked periodically so that if the
    heartbeat dies (connection lost), we stop processing before the
    watchdog reclaims us.
    """
    job_type = job.get("job_type", "gsd_task")

    # P-07: Check heartbeat health before starting expensive work
    if heartbeat.should_abort:
        raise RuntimeError("Heartbeat dead — aborting to prevent duplicate processing")

    if job_type == "gsd_task":
        # Import here to avoid circular imports
        from gsd_executor import run_gsd_pipeline
        return run_gsd_pipeline(conn, job, heartbeat)

    elif job_type == "lead_score":
        from lead_scorer import run_lead_scoring
        return run_lead_scoring(conn, job)

    elif job_type == "sdr_reply":
        from sdr_handler import run_sdr_reply
        return run_sdr_reply(conn, job)

    elif job_type == "discovery":
        from lead_pipeline import run_scheduled_discovery
        run_scheduled_discovery(conn)
        return 0.01  # Outscraper + enrichment cost estimate

    elif job_type == "outreach_batch":
        from lead_pipeline import send_approved_outreach
        payload = job.get("payload", {})
        campaign_id = payload.get("campaign_id", "")
        if not campaign_id:
            raise ValueError("outreach_batch job requires payload.campaign_id")
        send_approved_outreach(conn, campaign_id)
        return 0.0

    else:
        raise ValueError(f"Unknown job_type: {job_type}")


# ── Main worker loop ────────────────────────────────────────────────────────

def run_worker() -> None:
    """
    Long-running worker process. Claims jobs via SKIP LOCKED, enforces budget,
    runs heartbeat, reconciles costs, handles retries + DLQ.
    """
    conn = get_connection()
    log.info(f"Worker {WORKER_ID} started.")

    while not SHUTDOWN_FLAG.is_set():
        conn = get_or_reconnect(conn)  # P-06: reconnect if needed

        job = claim_job(conn)
        if not job:
            SHUTDOWN_FLAG.wait(timeout=5)  # Interruptible sleep
            continue

        job_id = str(job["id"])
        project_id = str(job["project_id"])
        estimated_cost = 0.05  # Conservative pre-estimate

        # Bug #2 fix: verify job_id exists before any log_audit call
        if not job_id:
            log.error("Claimed job has no id — skipping")
            continue

        # Budget gate (Bug #1: commit inside reserve_budget)
        if not reserve_budget(conn, estimated_cost, project_id):
            log_audit(conn, job_id, "processing", "pending", "budget_exceeded_requeue")
            continue

        # Start heartbeat (P-05: uses own connection)
        hb = HeartbeatThread(job_id)
        hb.start()

        actual_cost = 0.0
        try:
            actual_cost = execute_job(conn, job, hb)

            # P-08 fix: reconcile estimated vs actual cost
            reconcile_budget(conn, estimated_cost, actual_cost, project_id)

            log_audit(conn, job_id, "processing", "completed")
            log.info(f"Job {job_id} completed. Cost: ${actual_cost:.4f}")

        except Exception as e:
            log.error(f"Job {job_id} failed: {e}")
            release_budget(conn, estimated_cost, project_id)  # Bug #4: refund

            retry_count = job["retry_count"] + 1
            if retry_count >= job["max_retries"]:
                log_audit(conn, job_id, "processing", "dead_letter", str(e)[:1000])
                send_dlq_alert(conn, job_id, str(e))
            else:
                # Requeue for retry
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE jobs SET retry_count = %s WHERE id = %s",
                            (retry_count, job_id),
                        )
                    conn.commit()
                    log_audit(
                        conn, job_id, "processing", "pending",
                        f"retry_{retry_count}: {str(e)[:500]}",
                    )
                except Exception as retry_err:
                    conn.rollback()
                    log.error(f"Failed to requeue job {job_id}: {retry_err}")

        finally:
            hb.stop()

    # Graceful shutdown
    log.info(f"Worker {WORKER_ID} shutting down.")
    try:
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    run_worker()

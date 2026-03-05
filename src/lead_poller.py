"""
lead_poller.py — Background alert poller.

Polls the `alerts` table every POLL_INTERVAL_SECONDS for unread alerts
and sends them to Telegram. Marks each alert as read atomically.

This runs as a daemon thread alongside the main worker loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time

import psycopg2
from psycopg2.extras import RealDictCursor

log = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60
MAX_ALERTS_PER_BATCH = 10  # Don't flood Telegram in one burst


def _send_alerts_batch(alerts: list[dict]) -> None:
    """
    Send each alert to Telegram asynchronously.
    Imports telegram_bot here to avoid circular imports.

    Args:
        alerts: List of alert dicts with keys: alert_type, message, id.
    """
    from telegram_bot import send_alert

    for alert in alerts:
        try:
            asyncio.run(send_alert(alert["alert_type"], alert["message"]))
        except Exception as e:
            log.error(f"Failed to send alert {alert['id']} to Telegram: {e}")


def _poll_once(conn: psycopg2.extensions.connection) -> int:
    """
    Fetch up to MAX_ALERTS_PER_BATCH unread alerts, send them to Telegram,
    and mark them as read — all in one transaction.

    Args:
        conn: Live psycopg2 connection.

    Returns:
        Number of alerts processed.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # SKIP LOCKED prevents double-processing if two pollers run
            cur.execute(
                """SELECT id, alert_type, message
                   FROM alerts
                   WHERE is_read = FALSE
                   ORDER BY created_at ASC
                   LIMIT %s
                   FOR UPDATE SKIP LOCKED""",
                (MAX_ALERTS_PER_BATCH,),
            )
            alerts = [dict(row) for row in cur.fetchall()]

            if not alerts:
                conn.rollback()
                return 0

            alert_ids = [a["id"] for a in alerts]
            cur.execute(
                "UPDATE alerts SET is_read = TRUE WHERE id = ANY(%s)",
                (alert_ids,),
            )
        conn.commit()

        # Send after commit — idempotent if Telegram delivery fails
        _send_alerts_batch(alerts)
        log.info(f"Processed {len(alerts)} alert(s)")
        return len(alerts)

    except Exception as e:
        conn.rollback()
        log.error(f"Alert poll failed: {e}")
        return 0


class AlertPoller:
    """
    Background daemon that polls the alerts table and forwards to Telegram.

    Usage:
        poller = AlertPoller()
        poller.start()
        # ... later ...
        poller.stop()
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._conn: psycopg2.extensions.connection | None = None

    def start(self) -> None:
        """Start the polling thread."""
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="alert-poller"
        )
        self._thread.start()
        log.info("Alert poller started")

    def stop(self) -> None:
        """Signal the poller to stop and wait for thread to exit."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        log.info("Alert poller stopped")

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Return a healthy connection, reconnecting if needed."""
        if self._conn is not None:
            try:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
                self._conn.rollback()
                return self._conn
            except Exception:
                try:
                    self._conn.close()
                except Exception:
                    pass

        self._conn = psycopg2.connect(os.environ["DATABASE_URL"])
        self._conn.autocommit = False
        log.info("Alert poller reconnected to database")
        return self._conn

    def _run(self) -> None:
        """Main polling loop. Runs until stop() is called."""
        while not self._stop.is_set():
            try:
                conn = self._get_conn()
                _poll_once(conn)
            except Exception as e:
                log.error(f"Alert poller loop error: {e}")

            # Interruptible sleep — wakes up immediately on stop()
            self._stop.wait(timeout=POLL_INTERVAL_SECONDS)

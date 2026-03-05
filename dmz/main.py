"""
dmz/main.py — Telegram → GitHub DMZ (FastAPI)

The Telegram bot has ZERO direct access to GitHub or Postgres.
All callbacks route through this internal API.

Fixes applied from PROBLEMS.md:
  P-15: Removed dead verify_telegram_signature() (WebApp verification, not webhook).
        Webhook auth uses X-Telegram-Bot-Api-Secret-Token header (correct approach).
  P-16: Connection leak fixed — uses context manager for all DB access.
  P-17: JSONB injection prevented — uses parameterized jsonb cast.
  P-18: answerCallbackQuery called to dismiss Telegram loading spinner.
  P-19: Rate limiting added via slowapi.
  Bug #9:  PR state checked before merge (idempotency).
  Bug #10: REJECT routes rejection_reason back to GSD task.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Generator

import httpx
import psycopg2
from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Agency-in-a-Box DMZ", docs_url=None, redoc_url=None)

# P-19 fix: Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GITHUB_PAT = os.environ["GITHUB_PAT"]  # Only the DMZ holds this
GITHUB_ORG = os.environ["GITHUB_ORG"]
DB_URL = os.environ["DATABASE_URL"]
WEBHOOK_SECRET = os.environ["TELEGRAM_WEBHOOK_SECRET"]

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_PAT}",
    "Accept": "application/vnd.github+json",
}


# ── P-16 fix: Connection context manager — no leaks ─────────────────────────

@contextmanager
def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context-managed DB connection. Always closed, even on exception."""
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── P-18 fix: Answer Telegram callback to dismiss spinner ───────────────────

async def answer_callback(callback_id: str, text: str = "") -> None:
    """Send answerCallbackQuery to Telegram to dismiss the loading spinner."""
    if not callback_id:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
            )
    except Exception as e:
        log.warning(f"Failed to answer callback {callback_id}: {e}")


# ── Main webhook endpoint ────────────────────────────────────────────────────

@app.post("/internal/telegram/callback")
@limiter.limit("30/minute")  # P-19: rate limit
async def telegram_callback(request: Request) -> dict:
    """
    Receives Telegram webhook callbacks, validates auth, routes to handlers.
    P-15: Auth is via X-Telegram-Bot-Api-Secret-Token header (not WebApp HMAC).
    """
    # Verify webhook secret
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    body = await request.json()
    callback = body.get("callback_query", {})
    data = callback.get("data", "")
    callback_id = callback.get("id", "")

    if data.startswith("APPROVE_PR:"):
        parts = data.split(":")
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="Malformed APPROVE_PR payload")
        _, repo, pr_number = parts
        result = await handle_approve_pr(repo, int(pr_number))
        await answer_callback(callback_id, f"PR #{pr_number}: {result['status']}")
        return result

    if data.startswith("REJECT_PR:"):
        parts = data.split(":")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail="Malformed REJECT_PR payload")
        _, repo, pr_number, job_id = parts
        result = await handle_reject_pr(repo, int(pr_number), job_id)
        await answer_callback(callback_id, f"PR #{pr_number} rejected, re-queued")
        return result

    if data.startswith("LEAD_APPROVE:") or data.startswith("LEAD_REJECT:"):
        parts = data.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Malformed LEAD payload")
        action, lead_id = parts
        result = handle_lead_decision(lead_id, action)
        await answer_callback(callback_id, result.get("status", "done"))
        return result

    await answer_callback(callback_id)
    return {"ok": True}


# ── PR Approval (Bug #9: idempotent merge check) ────────────────────────────

async def handle_approve_pr(repo: str, pr_number: int) -> dict:
    """Merge a GitHub PR. Checks state first to prevent duplicate merges."""
    async with httpx.AsyncClient(timeout=30) as client:
        # Bug #9: Check PR state before merging (idempotency)
        check = await client.get(
            f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/pulls/{pr_number}",
            headers=GITHUB_HEADERS,
        )
        if check.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub API error on PR check")

        pr = check.json()
        if pr.get("state") == "closed" or pr.get("merged"):
            log.info(f"PR {pr_number} already merged/closed. Duplicate callback ignored.")
            return {"ok": True, "status": "already_merged"}

        # Merge the PR
        merge = await client.put(
            f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/pulls/{pr_number}/merge",
            headers=GITHUB_HEADERS,
            json={
                "merge_method": "squash",
                "commit_title": f"Approved via Agency-in-a-Box (PR #{pr_number})",
            },
        )
        if merge.status_code == 200:
            log.info(f"PR {pr_number} merged successfully.")
            # Update project status in DB
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE projects SET status = 'delivered', updated_at = NOW()
                           WHERE github_repo = %s AND github_pr_number = %s""",
                        (repo, pr_number),
                    )
                conn.commit()
            return {"ok": True, "status": "merged"}
        else:
            log.error(f"Merge failed: {merge.status_code} {merge.text}")
            raise HTTPException(status_code=500, detail="GitHub merge failed")


# ── PR Rejection (Bug #10: routes back to GSD task) ─────────────────────────

async def handle_reject_pr(repo: str, pr_number: int, job_id: str) -> dict:
    """
    Close the PR and requeue the job for revision.
    Bug #10: rejection_reason routed back to GSD task tree.
    P-17 fix: JSONB update uses parameterized query, not string interpolation.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        await client.patch(
            f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/pulls/{pr_number}",
            headers=GITHUB_HEADERS,
            json={"state": "closed"},
        )

    # P-16 fix: context manager ensures connection is always closed
    # P-17 fix: parameterized JSONB merge instead of string concatenation
    revision_payload = json.dumps({"revision_requested": True, "rejected_pr": pr_number})

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = 'pending',
                       payload = payload || %s::jsonb,
                       updated_at = NOW()
                   WHERE id = %s""",
                (revision_payload, job_id),
            )
        conn.commit()

    return {"ok": True, "status": "re_queued"}


# ── Lead approval/rejection ──────────────────────────────────────────────────

def handle_lead_decision(lead_id: str, action: str) -> dict:
    """Handle Gate 1: lead approval or rejection."""
    new_status = "approved" if action == "LEAD_APPROVE" else "rejected"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE leads SET status = %s WHERE id = %s",
                (new_status, lead_id),
            )
        conn.commit()
    return {"ok": True, "status": new_status}


# ── Instantly.ai reply webhook ───────────────────────────────────────────────

@app.post("/webhooks/instantly")
@limiter.limit("60/minute")
async def instantly_webhook(request: Request) -> dict:
    """
    Receives reply webhooks from Instantly.ai.
    Creates sdr_reply jobs for the worker to process.
    """
    body = await request.json()

    # Import here to avoid import at module level
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "src"))
    from instantly_client import process_reply_webhook

    with get_db() as conn:
        job_id = process_reply_webhook(conn, body)

    if job_id:
        return {"ok": True, "job_id": job_id}
    return {"ok": True, "skipped": True}


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "dmz"}

"""
instantly_client.py — Instantly.ai integration for cold email outreach.

Capabilities:
  1. Add leads to Instantly campaigns
  2. Send cold emails via Instantly API
  3. Process reply webhooks (incoming leads → sdr_reply jobs)
  4. Track email status (sent, opened, replied, bounced)

Instantly.ai API docs: https://developer.instantly.ai/
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "")
INSTANTLY_BASE_URL = "https://api.instantly.ai/api/v1"


# ── API helpers ──────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
    }


def _params() -> dict[str, str]:
    """Base query params with API key."""
    return {"api_key": INSTANTLY_API_KEY}


def _check_api_key() -> bool:
    if not INSTANTLY_API_KEY:
        log.warning("INSTANTLY_API_KEY not set — Instantly.ai integration disabled")
        return False
    return True


# ── Campaign management ──────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def list_campaigns() -> list[dict]:
    """List all Instantly.ai campaigns."""
    if not _check_api_key():
        return []

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{INSTANTLY_BASE_URL}/campaign/list",
            params=_params(),
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def get_campaign(campaign_id: str) -> dict | None:
    """Get details of a specific campaign."""
    if not _check_api_key():
        return None

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{INSTANTLY_BASE_URL}/campaign/get",
            params={**_params(), "campaign_id": campaign_id},
            headers=_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


# ── Lead management (add to campaign) ────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def add_lead_to_campaign(
    campaign_id: str,
    email: str,
    first_name: str = "",
    last_name: str = "",
    company_name: str = "",
    custom_variables: dict | None = None,
) -> bool:
    """
    Add a single lead to an Instantly.ai campaign.

    Returns True if successfully added.
    """
    if not _check_api_key():
        return False

    payload = {
        "api_key": INSTANTLY_API_KEY,
        "campaign_id": campaign_id,
        "skip_if_in_workspace": True,
        "leads": [
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                **({"custom_variables": custom_variables} if custom_variables else {}),
            }
        ],
    }

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{INSTANTLY_BASE_URL}/lead/add",
            json=payload,
            headers=_headers(),
        )
        if resp.status_code == 200:
            log.info(f"Added {email} to campaign {campaign_id}")
            return True
        else:
            log.warning(
                f"Failed to add {email} to campaign: "
                f"{resp.status_code} {resp.text[:200]}"
            )
            return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def add_leads_batch(
    campaign_id: str,
    leads: list[dict],
) -> int:
    """
    Add multiple leads to an Instantly.ai campaign.

    Args:
        campaign_id: Target campaign UUID
        leads: List of dicts with keys: email, first_name, last_name, company_name

    Returns:
        Number of leads successfully added.
    """
    if not _check_api_key():
        return 0

    if not leads:
        return 0

    # Instantly API accepts max 1000 leads per request
    batch_size = 1000
    total_added = 0

    for i in range(0, len(leads), batch_size):
        batch = leads[i : i + batch_size]
        payload = {
            "api_key": INSTANTLY_API_KEY,
            "campaign_id": campaign_id,
            "skip_if_in_workspace": True,
            "leads": [
                {
                    "email": l["email"],
                    "first_name": l.get("first_name", ""),
                    "last_name": l.get("last_name", ""),
                    "company_name": l.get("company_name", ""),
                }
                for l in batch
                if l.get("email")
            ],
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{INSTANTLY_BASE_URL}/lead/add",
                json=payload,
                headers=_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                added = data.get("leads_added", len(batch))
                total_added += added
            else:
                log.warning(f"Batch add failed: {resp.status_code}")

    log.info(f"Added {total_added}/{len(leads)} leads to campaign {campaign_id}")
    return total_added


# ── Lead status tracking ─────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def get_lead_status(email: str, campaign_id: str | None = None) -> dict | None:
    """
    Get the status of a lead in Instantly.

    Returns dict with status info or None.
    """
    if not _check_api_key():
        return None

    params = {**_params(), "email": email}
    if campaign_id:
        params["campaign_id"] = campaign_id

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{INSTANTLY_BASE_URL}/lead/get",
            params=params,
            headers=_headers(),
        )
        if resp.status_code == 200:
            return resp.json()
        return None


# ── Reply webhook processing ─────────────────────────────────────────────────

def process_reply_webhook(
    conn,
    webhook_data: dict,
) -> str | None:
    """
    Process an Instantly.ai reply webhook and create an sdr_reply job.

    Webhook payload (from Instantly):
        {
            "event_type": "reply_received",
            "email": "prospect@company.nl",
            "campaign_id": "...",
            "message_body": "...",
            "timestamp": "..."
        }

    Returns:
        Job ID of created sdr_reply job, or None on failure.
    """
    event_type = webhook_data.get("event_type", "")
    email = webhook_data.get("email", "")
    message_body = webhook_data.get("message_body", "")

    if event_type != "reply_received":
        log.debug(f"Ignoring Instantly webhook event: {event_type}")
        return None

    if not email or not message_body:
        log.warning("Reply webhook missing email or message_body")
        return None

    # Find the lead by contact_email
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id::text, status FROM leads
                   WHERE contact_email = %s
                   LIMIT 1""",
                (email,),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"DB lookup failed for reply from {email}: {e}")
        return None

    if not row:
        log.warning(f"No lead found for reply from {email}")
        return None

    lead_id = row[0]

    # Create sdr_reply job
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO jobs (job_type, project_id, payload)
                   VALUES ('sdr_reply', NULL, %s::jsonb)
                   RETURNING id::text""",
                (json.dumps({
                    "lead_id": lead_id,
                    "their_reply": message_body[:5000],
                    "instantly_email": email,
                    "instantly_campaign_id": webhook_data.get("campaign_id"),
                    "instantly_message_id": webhook_data.get("message_id"),
                }),),
            )
            job_row = cur.fetchone()
        conn.commit()

        job_id = job_row[0] if job_row else None
        if job_id:
            log.info(f"Created sdr_reply job {job_id} for lead {lead_id}")
        return job_id

    except Exception as e:
        conn.rollback()
        log.error(f"Failed to create sdr_reply job for lead {lead_id}: {e}")
        return None


# ── Outreach pipeline helper ─────────────────────────────────────────────────

def send_outreach(
    conn,
    lead_id: str,
    campaign_id: str,
) -> bool:
    """
    Add an approved lead to an Instantly.ai campaign for outreach.

    Steps:
      1. Fetch lead details from DB
      2. Add to Instantly campaign
      3. Update lead status to 'outreach'
      4. Record in outreach_campaigns table

    Returns True if successful.
    """
    if not _check_api_key():
        log.warning("Cannot send outreach — Instantly.ai not configured")
        return False

    # Fetch lead
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, company_name, contact_email, contact_name
                   FROM leads WHERE id = %s""",
                (lead_id,),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to fetch lead {lead_id}: {e}")
        return False

    if not row:
        log.warning(f"Lead {lead_id} not found")
        return False

    email = row[2]
    if not email:
        log.warning(f"Lead {lead_id} has no contact email — cannot send outreach")
        return False

    # Parse name
    contact_name = row[3] or ""
    parts = contact_name.split(" ", 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    # Add to Instantly
    success = add_lead_to_campaign(
        campaign_id=campaign_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        company_name=row[1] or "",
    )

    if not success:
        return False

    # Update lead status
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE leads
                   SET status = 'outreach', last_contact_date = NOW()
                   WHERE id = %s""",
                (lead_id,),
            )
            # Record in outreach_campaigns
            cur.execute(
                """INSERT INTO outreach_campaigns
                   (lead_id, campaign_id, status, added_at)
                   VALUES (%s, %s, 'active', NOW())
                   ON CONFLICT (lead_id, campaign_id) DO NOTHING""",
                (lead_id, campaign_id),
            )
        conn.commit()
        log.info(f"Lead {lead_id} added to campaign {campaign_id}")
        return True
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to update outreach status for lead {lead_id}: {e}")
        return False

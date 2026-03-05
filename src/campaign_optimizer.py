"""
campaign_optimizer.py — Pull performance metrics from Instantly.ai,
store snapshots in campaign_performance, and surface winning angles.

Runs on a daily schedule via campaign_sync job type.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from instantly_client import (
    list_campaigns,
    _check_api_key,
    _params,
    _headers,
    INSTANTLY_BASE_URL,
)

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


# ── Fetch campaign analytics from Instantly ──────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def _fetch_campaign_analytics(campaign_id: str) -> dict:
    """Get analytics for a single Instantly campaign."""
    if not _check_api_key():
        return {}

    resp = httpx.get(
        f"{INSTANTLY_BASE_URL}/campaign/get",
        params={**_params(), "campaign_id": campaign_id},
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "campaign_id": campaign_id,
        "campaign_name": data.get("name", ""),
        "status": data.get("status", "unknown"),
        "emails_sent": data.get("emails_sent_count", 0),
        "opens": data.get("emails_open_count", 0),
        "clicks": data.get("emails_click_count", 0),
        "replies": data.get("emails_reply_count", 0),
        "bounces": data.get("bounced_count", 0),
    }


# ── Derive winning angles ───────────────────────────────────────────────────

def _compute_winning_angles(snapshots: list[dict]) -> list[dict]:
    """Rank campaigns by reply rate and return top performers as 'winning angles'."""
    angles: list[dict] = []
    for s in snapshots:
        sent = s.get("emails_sent", 0)
        if sent < 10:
            continue  # not enough data
        reply_rate = (s.get("replies", 0) / sent) * 100
        open_rate = (s.get("opens", 0) / sent) * 100
        angles.append({
            "campaign_id": s["campaign_id"],
            "campaign_name": s.get("campaign_name", ""),
            "reply_rate": round(reply_rate, 2),
            "open_rate": round(open_rate, 2),
            "sent": sent,
            "replies": s.get("replies", 0),
        })

    # Sort by reply_rate descending
    angles.sort(key=lambda a: a["reply_rate"], reverse=True)
    return angles[:10]  # top 10


# ── Entry point for worker_core ──────────────────────────────────────────────

def run_campaign_sync(conn, job: dict) -> float:
    """Execute a campaign_sync job.

    Payload: {} (no args needed — syncs all active campaigns)
    """
    if not _check_api_key():
        log.warning("Instantly API key not set — skipping campaign sync")
        return 0.0

    try:
        campaigns = list_campaigns()
    except Exception as e:
        log.error(f"Failed to list Instantly campaigns: {e}")
        return 0.0

    if not campaigns:
        log.info("No campaigns found in Instantly")
        return 0.0

    snapshots: list[dict] = []
    api_calls = 1  # list_campaigns counts as 1

    for camp in campaigns:
        camp_id = camp.get("id", "")
        if not camp_id:
            continue

        try:
            analytics = _fetch_campaign_analytics(camp_id)
            api_calls += 1
            if analytics:
                snapshots.append(analytics)

                # Upsert into campaign_performance
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO campaign_performance
                           (campaign_id, snapshot_date, emails_sent, opens,
                            clicks, replies, bounces)
                           VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s)
                           ON CONFLICT (campaign_id, snapshot_date)
                           DO UPDATE SET
                             emails_sent = EXCLUDED.emails_sent,
                             opens = EXCLUDED.opens,
                             clicks = EXCLUDED.clicks,
                             replies = EXCLUDED.replies,
                             bounces = EXCLUDED.bounces,
                             fetched_at = NOW()""",
                        (
                            camp_id,
                            analytics.get("emails_sent", 0),
                            analytics.get("opens", 0),
                            analytics.get("clicks", 0),
                            analytics.get("replies", 0),
                            analytics.get("bounces", 0),
                        ),
                    )
                conn.commit()

        except Exception as e:
            conn.rollback()
            log.error(f"Failed to fetch analytics for campaign {camp_id}: {e}")

    # Compute and log winning angles
    angles = _compute_winning_angles(snapshots)
    if angles:
        log.info(
            f"Top winning angle: {angles[0]['campaign_name']} "
            f"({angles[0]['reply_rate']}% reply rate)"
        )

    cost = api_calls * 0.0  # Instantly API is free
    log.info(f"Campaign sync complete. {len(snapshots)} campaigns synced.")
    return cost

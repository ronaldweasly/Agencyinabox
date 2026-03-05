"""
competitor_monitor.py — Track what competitors are doing so the SDR can
mention specific weaknesses in outreach.

For each lead, searches for the lead's top competitors and extracts:
  - Ad copy snippets (Google Ads)
  - Pricing signals
  - Feature gaps vs. our offering
  - Review weaknesses (low ratings, complaints)

Stores findings in competitor_signals table and as JSONB on leads.competitor_intel.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_serper_key

log = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"

# Competitor URLs to always monitor (set via env / config)
COMPETITOR_URLS: list[str] = [
    u.strip()
    for u in os.environ.get("COMPETITOR_URLS", "").split(",")
    if u.strip()
]


# ── Serper helpers ───────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _serper_search(query: str, num: int = 5) -> list[dict]:
    api_key = get_serper_key()
    if not api_key:
        log.debug("SERPER_API_KEY not set — skipping competitor search")
        return []

    resp = httpx.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("organic", [])


# ── Signal extraction ────────────────────────────────────────────────────────

WEAKNESS_KEYWORDS = [
    "slow", "expensive", "bad support", "outdated", "unreliable",
    "poor communication", "overpriced", "no response", "terrible",
]


def _extract_competitor_signals(
    results: list[dict],
    competitor_name: str,
) -> list[dict]:
    """Parse search results into structured competitor signals."""
    signals: list[dict] = []
    for r in results:
        snippet = r.get("snippet", "")
        title = r.get("title", "")
        url = r.get("link", "")
        combined = (snippet + " " + title).lower()

        signal_type = "general"
        if any(kw in combined for kw in ("pricing", "cost", "price", "$", "quote")):
            signal_type = "pricing"
        elif any(kw in combined for kw in ("review", "rating", "stars", "complaint")):
            signal_type = "review_weakness"
        elif any(kw in combined for kw in ("feature", "service", "offer", "solution")):
            signal_type = "feature_gap"
        elif any(kw in combined for kw in ("ad", "sponsored", "promotion")):
            signal_type = "ad_copy"

        # Check for weakness mentions
        has_weakness = any(kw in combined for kw in WEAKNESS_KEYWORDS)

        if signal_type != "general" or has_weakness:
            signals.append({
                "competitor_name": competitor_name,
                "competitor_url": url,
                "signal_type": signal_type,
                "detail": snippet[:300],
                "has_weakness": has_weakness,
                "found_at": datetime.now(timezone.utc).isoformat(),
            })

    return signals


# ── Core function ────────────────────────────────────────────────────────────

def scan_competitors(lead: dict) -> list[dict]:
    """Find competitor intel relevant to a single lead."""
    category = lead.get("category", "")
    city = lead.get("city", "")
    company = lead.get("company_name", "")

    if not category and not company:
        return []

    queries = []
    if category and city:
        queries.append(f'"{category}" "{city}" reviews OR pricing')
        queries.append(f'"{category}" "{city}" complaints OR "bad experience"')
    if company:
        queries.append(f'"{company}" competitors OR alternatives')

    all_signals: list[dict] = []
    for q in queries:
        results = _serper_search(q, num=5)
        # Use category as competitor proxy
        name = category or company
        all_signals.extend(_extract_competitor_signals(results, name))

    return all_signals


# ── Entry point for worker_core ──────────────────────────────────────────────

def run_competitor_scan(conn, job: dict) -> float:
    """Execute a competitor_scan job.

    Payload: {"lead_ids": ["uuid1", ...]}
    """
    payload = job.get("payload", {})
    lead_ids = payload.get("lead_ids", [])
    if not lead_ids:
        log.warning(f"competitor_scan job {job['id']} has no lead_ids")
        return 0.0

    api_calls = 0
    for lead_id in lead_ids:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, company_name, website, category, city
                   FROM leads WHERE id = %s""",
                (lead_id,),
            )
            row = cur.fetchone()
        conn.commit()

        if not row:
            continue

        lead = {
            "id": str(row[0]),
            "company_name": row[1],
            "website": row[2],
            "category": row[3],
            "city": row[4],
        }

        try:
            signals = scan_competitors(lead)
            api_calls += 3  # up to 3 queries per lead

            # Store in competitor_signals table
            for sig in signals:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO competitor_signals
                           (lead_id, competitor_name, competitor_url,
                            signal_type, detail)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (
                            lead_id,
                            sig["competitor_name"],
                            sig["competitor_url"],
                            sig["signal_type"],
                            sig["detail"],
                        ),
                    )
                conn.commit()

            # Also store summary on the lead itself
            if signals:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE leads
                           SET competitor_intel = %s
                           WHERE id = %s""",
                        (json.dumps(signals[:5]), lead_id),  # top 5 signals
                    )
                conn.commit()
                log.info(f"Lead {lead_id}: {len(signals)} competitor signals stored")

        except Exception as e:
            conn.rollback()
            log.error(f"Competitor scan failed for {lead_id}: {e}")

    cost = api_calls * 0.001
    log.info(f"Competitor scan complete. {api_calls} API calls, ~${cost:.4f}")
    return cost

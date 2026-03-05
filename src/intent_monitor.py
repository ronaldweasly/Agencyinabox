"""
intent_monitor.py — Detect buying-intent signals for a lead.

Checks:
  1. Google News mentions (hiring, funding, expansion)
  2. Job postings (via Serper API if available)
  3. Technology changes (new stack detected vs. last enrichment)

Stores signals as JSONB on leads.intent_signals for the scorer and SDR
to reference in follow-ups.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"


# ── Serper Google search ─────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _serper_search(query: str, num: int = 5) -> list[dict]:
    """Run a Google search via Serper and return organic results."""
    if not SERPER_API_KEY:
        log.debug("SERPER_API_KEY not set — skipping search")
        return []

    resp = httpx.post(
        SERPER_URL,
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("organic", [])


# ── Signal detection ─────────────────────────────────────────────────────────

INTENT_KEYWORDS = {
    "hiring": ["hiring", "job opening", "careers page", "we're growing"],
    "funding": ["raised", "funding round", "series a", "series b", "investment"],
    "expansion": ["new location", "expanding", "new office", "grand opening"],
    "tech_change": ["migrating to", "switched to", "launched new website", "redesign"],
    "pain": ["looking for", "need help with", "searching for agency", "RFP"],
}


def _detect_signals(results: list[dict], company_name: str) -> list[dict]:
    """Scan search results for intent keywords and return signal dicts."""
    signals: list[dict] = []
    for r in results:
        snippet = (r.get("snippet", "") + " " + r.get("title", "")).lower()
        for category, keywords in INTENT_KEYWORDS.items():
            if any(kw in snippet for kw in keywords):
                signals.append({
                    "type": category,
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
                break  # one signal per result
    return signals


# ── Core function ────────────────────────────────────────────────────────────

def scan_intent(lead: dict) -> list[dict]:
    """Return a list of intent-signal dicts for one lead."""
    company = lead.get("company_name", "")
    city = lead.get("city", "")
    if not company:
        return []

    queries = [
        f'"{company}" hiring OR "job opening"',
        f'"{company}" funding OR investment',
        f'"{company}" {city} expansion OR "new location"',
    ]

    all_signals: list[dict] = []
    for q in queries:
        results = _serper_search(q, num=3)
        all_signals.extend(_detect_signals(results, company))

    return all_signals


# ── Entry point for worker_core ──────────────────────────────────────────────

def run_intent_scan(conn, job: dict) -> float:
    """Execute an intent_scan job.

    Payload: {"lead_ids": ["uuid1", ...]}
    """
    payload = job.get("payload", {})
    lead_ids = payload.get("lead_ids", [])
    if not lead_ids:
        log.warning(f"intent_scan job {job['id']} has no lead_ids")
        return 0.0

    api_calls = 0
    for lead_id in lead_ids:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, company_name, website, city
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
            "city": row[3],
        }

        try:
            signals = scan_intent(lead)
            api_calls += 3  # 3 queries per lead

            if signals:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE leads
                           SET intent_signals = %s
                           WHERE id = %s""",
                        (json.dumps(signals), lead_id),
                    )
                conn.commit()
                log.info(f"Lead {lead_id}: {len(signals)} intent signals found")
            else:
                log.debug(f"Lead {lead_id}: no intent signals")

        except Exception as e:
            conn.rollback()
            log.error(f"Intent scan failed for {lead_id}: {e}")

    # Serper costs ~$0.001 per search
    cost = api_calls * 0.001
    log.info(f"Intent scan complete. {api_calls} API calls, ~${cost:.4f}")
    return cost

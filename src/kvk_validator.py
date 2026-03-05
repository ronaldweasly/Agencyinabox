"""
kvk_validator.py — Dutch Chamber of Commerce (KvK) validation.

Validates that a company is legitimately registered in the Netherlands
before cold outreach. This is both a GDPR safeguard (legitimate interest
requires a real B2B entity) and a quality filter.

Data sources:
  1. KvK Open Data API (api.kvk.nl) — official, requires API key
  2. Fallback: basic website + domain checks

KvK numbers are 8 digits (e.g. 12345678).
"""
from __future__ import annotations

import logging
import os
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

KVK_API_KEY = os.environ.get("KVK_API_KEY", "")
KVK_API_BASE = "https://api.kvk.nl/api/v1"

# Pre-compiled pattern for KvK number
KVK_NUMBER_RE = re.compile(r"^\d{8}$")


# ── KvK API lookup ───────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def search_kvk_by_name(
    company_name: str,
    city: str | None = None,
) -> list[dict]:
    """
    Search KvK registry by company name.

    Returns list of matches with keys:
      - kvk_number: str (8-digit)
      - trade_name: str
      - city: str
      - is_active: bool

    Empty list if no API key or no results.
    """
    if not KVK_API_KEY:
        log.warning("KVK_API_KEY not set — skipping KvK validation")
        return []

    params: dict[str, str] = {
        "handelsnaam": company_name,
        "pagina": "1",
        "resultatenPerPagina": "5",
    }
    if city:
        params["plaats"] = city

    headers = {"apikey": KVK_API_KEY}

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{KVK_API_BASE}/zoeken",
            params=params,
            headers=headers,
        )
        if resp.status_code == 404:
            return []
        if resp.status_code == 429:
            log.warning("KvK API rate limited")
            raise httpx.HTTPStatusError(
                "Rate limited", request=resp.request, response=resp
            )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("resultaten", []):
        kvk_number = item.get("kvkNummer", "")
        trade_name = item.get("handelsnaam", "")
        addresses = item.get("adres", {})
        result_city = ""
        if isinstance(addresses, dict):
            result_city = addresses.get("plaats", "")
        elif isinstance(addresses, list) and addresses:
            result_city = addresses[0].get("plaats", "")

        results.append({
            "kvk_number": kvk_number,
            "trade_name": trade_name,
            "city": result_city,
            "is_active": item.get("actief", "Ja") == "Ja",
        })

    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def lookup_kvk_number(kvk_number: str) -> dict | None:
    """
    Look up a specific KvK number for detailed company profile.

    Returns dict with company info or None if not found.
    """
    if not KVK_API_KEY:
        return None

    if not KVK_NUMBER_RE.match(kvk_number):
        log.warning(f"Invalid KvK number format: {kvk_number}")
        return None

    headers = {"apikey": KVK_API_KEY}

    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{KVK_API_BASE}/basisprofielen/{kvk_number}",
            headers=headers,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

    return {
        "kvk_number": data.get("kvkNummer"),
        "trade_name": data.get("handelsnaam"),
        "legal_form": data.get("rechtsvorm"),
        "is_active": data.get("actief", "Ja") == "Ja",
        "total_employees": data.get("totaalWerkzamePersonen"),
        "sbi_codes": [
            sbi.get("sbiCode") for sbi in data.get("spiActiviteiten", [])
        ],
    }


# ── Validation logic ─────────────────────────────────────────────────────────

def validate_lead(
    company_name: str,
    website: str | None = None,
    city: str | None = None,
) -> dict:
    """
    Validate a lead against the KvK registry.

    Returns:
        {
            "validated": bool,
            "kvk_number": str | None,
            "confidence": str,  # "high", "medium", "low", "none"
            "reason": str
        }
    """
    # Try KvK API first
    try:
        matches = search_kvk_by_name(company_name, city=city)
    except Exception as e:
        log.error(f"KvK search failed for '{company_name}': {e}")
        return {
            "validated": False,
            "kvk_number": None,
            "confidence": "none",
            "reason": f"KvK API error: {str(e)[:200]}",
        }

    if not matches:
        # No API key or no results — apply basic heuristics
        return _fallback_validation(company_name, website)

    # Find best match
    best = _find_best_match(company_name, matches, city)
    if best:
        return {
            "validated": True,
            "kvk_number": best["kvk_number"],
            "confidence": "high" if best.get("_exact_match") else "medium",
            "reason": f"KvK match: {best['trade_name']} ({best['kvk_number']})",
        }

    return {
        "validated": False,
        "kvk_number": None,
        "confidence": "low",
        "reason": f"KvK search returned {len(matches)} results but no confident match",
    }


def _find_best_match(
    company_name: str,
    matches: list[dict],
    city: str | None,
) -> dict | None:
    """Find the best KvK match for a company name."""
    name_lower = company_name.lower().strip()

    for match in matches:
        if not match.get("is_active", True):
            continue

        trade_lower = match.get("trade_name", "").lower().strip()

        # Exact or near-exact match
        if trade_lower == name_lower or trade_lower.startswith(name_lower):
            match["_exact_match"] = True
            return match

        # City match increases confidence
        if city and match.get("city", "").lower() == city.lower():
            match["_exact_match"] = False
            return match

    # Return first active result if nothing better
    for match in matches:
        if match.get("is_active", True):
            match["_exact_match"] = False
            return match

    return None


def _fallback_validation(company_name: str, website: str | None) -> dict:
    """
    Basic heuristic validation when KvK API is unavailable.
    Checks:
      1. Company name looks real (not generic/spam)
      2. Website has a Dutch TLD (.nl) or common business TLD
    """
    # Name quality checks
    name = company_name.strip().lower()
    if len(name) < 2:
        return {
            "validated": False,
            "kvk_number": None,
            "confidence": "none",
            "reason": "Company name too short",
        }

    spam_indicators = ["test", "example", "asdf", "xxx", "null"]
    if any(spam in name for spam in spam_indicators):
        return {
            "validated": False,
            "kvk_number": None,
            "confidence": "none",
            "reason": "Company name looks like test/spam data",
        }

    # Dutch TLD check
    confidence = "low"
    reason = "No KvK API — basic heuristic only"

    if website:
        domain = website.lower()
        if ".nl" in domain:
            confidence = "medium"
            reason = "Dutch .nl domain detected (no KvK API for verification)"
        elif any(tld in domain for tld in [".com", ".eu", ".io", ".tech"]):
            confidence = "low"
            reason = "Non-.nl domain — might not be Dutch entity"

    return {
        "validated": confidence != "none",
        "kvk_number": None,
        "confidence": confidence,
        "reason": reason,
    }


# ── DB update helper ─────────────────────────────────────────────────────────

def mark_lead_validated(
    conn,
    lead_id: str,
    kvk_result: dict,
) -> None:
    """Update lead with KvK validation result."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE leads
                   SET kvk_validated = %s, updated_at = NOW()
                   WHERE id = %s""",
                (kvk_result["validated"], lead_id),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to update KvK validation for lead {lead_id}: {e}")

"""
gdpr_utils.py — GDPR-compliant data handling utilities.

Core capabilities:
  1. Peppered SHA-256 domain hashing for lead dedup (no raw domains stored).
  2. Data anonymization for lead records past retention.
  3. Consent state tracking helpers.
  4. PII scrubbing from log/audit payloads.

Security:
  - DOMAIN_PEPPER is loaded from Doppler at runtime. If leaked, re-hash all
    existing domain_hash values via a one-off migration.
  - Hashes are hex-encoded (64 chars) — safe for TEXT columns and indexing.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from urllib.parse import urlparse

log = logging.getLogger(__name__)

# ── Domain hashing (peppered SHA-256) ────────────────────────────────────────


def _get_pepper() -> str:
    """Load the domain pepper from environment. Fail loud if missing."""
    pepper = os.environ.get("DOMAIN_PEPPER", "")
    if not pepper:
        raise RuntimeError(
            "DOMAIN_PEPPER not set. Cannot hash domains without pepper."
        )
    return pepper


def extract_domain(url_or_email: str) -> str:
    """
    Extract a normalised root domain from a URL or email address.

    Examples:
        "https://www.acme.nl/about"  → "acme.nl"
        "info@acme.nl"               → "acme.nl"
        "acme.nl"                    → "acme.nl"
    """
    text = url_or_email.strip().lower()

    # Email?
    if "@" in text:
        text = text.split("@", 1)[1]

    # Full URL?
    if "://" in text:
        parsed = urlparse(text)
        text = parsed.hostname or text
    else:
        # Might have path attached: "acme.nl/about"
        text = text.split("/", 1)[0]

    # Strip www prefix
    if text.startswith("www."):
        text = text[4:]

    return text


def hash_domain(url_or_email: str) -> str:
    """
    Produce a peppered SHA-256 hex digest for a domain.
    Used as the dedup key in leads.domain_hash.

    >>> len(hash_domain("https://acme.nl"))
    64
    """
    domain = extract_domain(url_or_email)
    pepper = _get_pepper()
    salted = f"{pepper}:{domain}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def verify_domain_hash(url_or_email: str, expected_hash: str) -> bool:
    """Check if a URL/email matches a stored domain_hash."""
    return hash_domain(url_or_email) == expected_hash


# ── PII scrubbing ────────────────────────────────────────────────────────────

# Patterns that look like PII
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+31|0031|06)[\s.-]?\d[\s.-]?\d[\s.-]?\d[\s.-]?\d[\s.-]?\d[\s.-]?\d[\s.-]?\d[\s.-]?\d?"
)
_KVK_RE = re.compile(r"\b\d{8}\b")  # KvK numbers are 8 digits


def scrub_pii(text: str) -> str:
    """
    Remove obvious PII from free-text fields (log messages, error strings).

    Replaces:
      - Email addresses → [EMAIL]
      - Dutch phone numbers → [PHONE]
      - KvK-like 8-digit numbers → [KVK]

    This is a best-effort filter for audit/log safety — NOT a substitute
    for proper data classification.
    """
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    # KvK pattern is aggressive — only scrub in known PII contexts
    # (caller decides whether to include KvK scrubbing)
    return text


def scrub_pii_with_kvk(text: str) -> str:
    """Like scrub_pii but also redacts 8-digit KvK numbers."""
    text = scrub_pii(text)
    text = _KVK_RE.sub("[KVK]", text)
    return text


# ── Anonymization ────────────────────────────────────────────────────────────


def anonymize_lead_record(lead_row: dict) -> dict:
    """
    Strip PII from a lead record for GDPR deletion.
    Preserves: id, domain_hash, status, icp_score, created_at.
    Clears:    company_name, website, contact_email, contact_name, icp_reasoning.

    Used by sql/003_gdpr.sql's application-level complement.
    """
    anonymized = dict(lead_row)
    pii_fields = [
        "company_name",
        "website",
        "contact_email",
        "contact_name",
        "icp_reasoning",
    ]
    for field in pii_fields:
        if field in anonymized:
            anonymized[field] = None
    return anonymized


# ── Consent helpers ──────────────────────────────────────────────────────────


def check_legitimate_interest(lead_status: str) -> bool:
    """
    Under GDPR Article 6(1)(f), legitimate interest applies for B2B
    prospecting while the lead is in active sales flow.

    Returns True if processing is allowed under legitimate interest.
    """
    allowed = {"new", "scored", "approved", "outreach", "replied", "qualified"}
    return lead_status in allowed


def is_past_retention(
    created_at_iso: str,
    last_contact_iso: str | None,
    converted: bool,
    retention_days: int = 90,
    converted_retention_days: int = 365,
) -> bool:
    """
    Check if a lead record is past its GDPR retention window.

    - Unconverted leads: 90 days from last contact (or creation if no contact).
    - Converted leads: 365 days from last contact.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    anchor_str = last_contact_iso or created_at_iso
    try:
        anchor = datetime.fromisoformat(anchor_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # Can't parse — treat as expired for safety
        return True

    days = converted_retention_days if converted else retention_days
    return now > anchor + timedelta(days=days)

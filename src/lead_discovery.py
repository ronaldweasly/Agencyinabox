"""
lead_discovery.py — Lead discovery pipeline: scrape → enrich → dedup → store.

Data sources (waterfall — first valid email wins):
  1. Outscraper Google Maps API — scrape Dutch businesses by niche + city
  2. Apollo.io — enrich with contact email + company data
  3. AnyMail Finder — fallback email discovery

GDPR compliance:
  - Domains are stored as peppered SHA-256 hashes (never raw).
  - Duplicate leads are rejected at insert time via UNIQUE on domain_hash.
  - All scraping limited to publicly available B2B data.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from gdpr_utils import extract_domain, hash_domain

log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

OUTSCRAPER_API_KEY = os.environ.get("OUTSCRAPER_API_KEY", "")
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
ANYMAIL_API_KEY = os.environ.get("ANYMAIL_API_KEY", "")


@dataclass
class RawLead:
    """Intermediate lead before DB insertion."""
    company_name: str
    website: str
    domain: str
    domain_hash: str
    contact_email: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    city: str | None = None
    category: str | None = None


# ── Outscraper Google Maps scraper ───────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def scrape_google_maps(
    query: str,
    region: str = "NL",
    limit: int = 20,
) -> list[RawLead]:
    """
    Scrape Google Maps via Outscraper API for Dutch businesses.

    Args:
        query: Search query, e.g. "IT consultancy Amsterdam"
        region: ISO country code (default NL)
        limit: Max results to return

    Returns:
        List of RawLead with company_name, website, domain_hash.
    """
    if not OUTSCRAPER_API_KEY:
        log.warning("OUTSCRAPER_API_KEY not set — returning empty results")
        return []

    url = "https://api.app.outscraper.com/maps/search-v3"
    params = {
        "query": query,
        "region": region,
        "limit": limit,
        "language": "nl",
        "async": "false",
    }
    headers = {"X-API-KEY": OUTSCRAPER_API_KEY}

    leads: list[RawLead] = []
    with httpx.Client(timeout=60) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Outscraper returns nested array: data.data[0] is the result set
    results = data.get("data", [[]])[0] if isinstance(data.get("data"), list) else []

    for biz in results:
        website = biz.get("site") or biz.get("website") or ""
        if not website:
            continue  # Can't dedup without a website

        domain = extract_domain(website)
        if not domain or "." not in domain:
            continue

        leads.append(
            RawLead(
                company_name=biz.get("name", "Unknown"),
                website=website,
                domain=domain,
                domain_hash=hash_domain(website),
                phone=biz.get("phone"),
                city=biz.get("city"),
                category=biz.get("category"),
            )
        )

    log.info(f"Outscraper returned {len(leads)} leads for query '{query}'")
    return leads


# ── Apollo.io enrichment ─────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def enrich_with_apollo(domain: str) -> dict:
    """
    Enrich a single domain with Apollo.io company + contact data.

    Returns dict with keys: contact_email, contact_name, company_info.
    Empty dict if not found or API unavailable.
    """
    if not APOLLO_API_KEY:
        log.debug("APOLLO_API_KEY not set — skipping Apollo enrichment")
        return {}

    url = "https://api.apollo.io/v1/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_domains": domain,
        "page": 1,
        "per_page": 1,
        "person_titles": ["CEO", "CTO", "Owner", "Managing Director", "Eigenaar"],
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code == 429:
            log.warning("Apollo.io rate limited — backing off")
            raise httpx.HTTPStatusError(
                "Rate limited", request=resp.request, response=resp
            )
        if resp.status_code != 200:
            return {}
        data = resp.json()

    people = data.get("people", [])
    if not people:
        return {}

    person = people[0]
    return {
        "contact_email": person.get("email"),
        "contact_name": person.get("name"),
        "title": person.get("title"),
        "company_name": person.get("organization", {}).get("name"),
    }


# ── AnyMail Finder fallback ─────────────────────────────────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
def find_email_anymail(domain: str) -> str | None:
    """
    Fallback email finder via AnyMail Finder API.
    Returns a verified email or None.
    """
    if not ANYMAIL_API_KEY:
        log.debug("ANYMAIL_API_KEY not set — skipping AnyMail lookup")
        return None

    url = "https://api.anymailfinder.com/v5.0/search/company.json"
    headers = {"Authorization": f"Bearer {ANYMAIL_API_KEY}"}
    payload = {"domain": domain}

    with httpx.Client(timeout=20) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()

    # AnyMail returns emails_found with verification status
    emails = data.get("emails", [])
    if not emails:
        return data.get("email")  # Sometimes returned at top level
    # Prefer verified
    for e in emails:
        if isinstance(e, dict) and e.get("verified"):
            return e.get("email")
    # Fall back to first
    if isinstance(emails[0], dict):
        return emails[0].get("email")
    return emails[0] if isinstance(emails[0], str) else None


# ── Enrichment waterfall ─────────────────────────────────────────────────────

def enrich_lead(lead: RawLead) -> RawLead:
    """
    Enrich a raw lead through the data waterfall:
      1. Apollo.io for email + contact name
      2. AnyMail Finder as fallback if Apollo has no email

    Mutates and returns the lead.
    """
    # Step 1: Apollo
    try:
        apollo_data = enrich_with_apollo(lead.domain)
        if apollo_data.get("contact_email"):
            lead.contact_email = apollo_data["contact_email"]
            lead.contact_name = apollo_data.get("contact_name", lead.contact_name)
            if apollo_data.get("company_name"):
                lead.company_name = apollo_data["company_name"]
            log.debug(f"Apollo enriched {lead.domain}: {lead.contact_email}")
            return lead
    except Exception as e:
        log.warning(f"Apollo enrichment failed for {lead.domain}: {e}")

    # Step 2: AnyMail fallback
    try:
        email = find_email_anymail(lead.domain)
        if email:
            lead.contact_email = email
            log.debug(f"AnyMail found email for {lead.domain}: {email}")
    except Exception as e:
        log.warning(f"AnyMail lookup failed for {lead.domain}: {e}")

    return lead


# ── Store leads to DB ────────────────────────────────────────────────────────

def store_leads(
    conn,
    leads: list[RawLead],
) -> tuple[int, int]:
    """
    Insert enriched leads into the database. Skips duplicates via domain_hash.

    Returns:
        (inserted_count, skipped_count)
    """
    inserted = 0
    skipped = 0

    for lead in leads:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO leads
                       (domain_hash, company_name, website,
                        contact_email, contact_name, status)
                       VALUES (%s, %s, %s, %s, %s, 'new')
                       ON CONFLICT (domain_hash) DO NOTHING
                       RETURNING id""",
                    (
                        lead.domain_hash,
                        lead.company_name,
                        lead.website,
                        lead.contact_email,
                        lead.contact_name,
                    ),
                )
                result = cur.fetchone()
            conn.commit()

            if result:
                inserted += 1
            else:
                skipped += 1
                log.debug(f"Duplicate lead skipped: {lead.domain}")

        except Exception as e:
            conn.rollback()
            log.error(f"Failed to store lead {lead.company_name}: {e}")
            skipped += 1

    log.info(f"Stored {inserted} new leads, skipped {skipped} duplicates")
    return inserted, skipped


# ── Discovery pipeline (called by lead_pipeline.py) ──────────────────────────

def run_discovery(
    conn,
    queries: list[str],
    region: str = "NL",
    limit_per_query: int = 20,
) -> list[str]:
    """
    Full discovery pipeline: scrape → enrich → dedup → store.

    Args:
        conn: psycopg2 connection
        queries: Search queries (e.g. ["IT consultant Amsterdam", "webshop Utrecht"])
        region: ISO country code
        limit_per_query: Max results per query

    Returns:
        List of new lead UUIDs that were successfully inserted.
    """
    all_leads: list[RawLead] = []

    # Scrape
    for query in queries:
        try:
            raw = scrape_google_maps(query, region=region, limit=limit_per_query)
            all_leads.extend(raw)
        except Exception as e:
            log.error(f"Scraping failed for query '{query}': {e}")

    if not all_leads:
        log.warning("No leads discovered from any query")
        return []

    # Deduplicate within batch by domain_hash
    seen_hashes: set[str] = set()
    unique_leads: list[RawLead] = []
    for lead in all_leads:
        if lead.domain_hash not in seen_hashes:
            seen_hashes.add(lead.domain_hash)
            unique_leads.append(lead)

    log.info(
        f"Discovered {len(all_leads)} total, {len(unique_leads)} unique leads"
    )

    # Enrich
    enriched: list[RawLead] = []
    for lead in unique_leads:
        enriched.append(enrich_lead(lead))

    # Store
    inserted, skipped = store_leads(conn, enriched)

    # Retrieve IDs of newly inserted leads
    new_ids: list[str] = []
    if inserted > 0:
        hashes = [l.domain_hash for l in enriched]
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id::text FROM leads
                   WHERE domain_hash = ANY(%s) AND status = 'new'""",
                (hashes,),
            )
            new_ids = [row[0] for row in cur.fetchall()]
        conn.commit()

    return new_ids

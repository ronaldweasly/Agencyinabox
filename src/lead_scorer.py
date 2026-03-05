"""
lead_scorer.py — ICP scoring engine powered by Gemini 2.0 Flash.

Scores each lead 0–100 against the client's Ideal Customer Profile (ICP).
Provides structured reasoning for human review at Gate 1.

ICP criteria (Dutch B2B SaaS/agency market):
  - Company type matches target niche
  - Has active website with clear service offering
  - Located in Netherlands (KvK validated preferred)
  - Has reachable decision-maker email
  - Company size / revenue signals
"""
from __future__ import annotations

import json
import logging
import os

import google.genai as genai
from instructor import from_genai, Mode
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agency_config import AGENCY_CONFIG, agency_prompt_snippet

log = logging.getLogger(__name__)

# ── Gemini client ────────────────────────────────────────────────────────────

gemini_client = from_genai(
    client=genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "")),
    mode=Mode.GENAI_TOOLS,
)


# ── Scoring schema ───────────────────────────────────────────────────────────

class ICPScore(BaseModel):
    """Structured output from the ICP scoring model."""
    score: int = Field(ge=0, le=100, description="ICP fit score 0-100")
    reasoning: str = Field(
        max_length=1000,
        description="Why this lead scored this way — shown to human at Gate 1",
    )
    niche_match: bool = Field(description="Does the company match target niche?")
    has_decision_maker: bool = Field(description="Is there a reachable decision maker?")
    dutch_entity: bool = Field(description="Is this a Netherlands-based entity?")
    red_flags: list[str] = Field(
        default_factory=list,
        description="Any concerns (competitor, nonprofit, spam, etc.)",
    )
    recommended_action: str = Field(
        description="'approve', 'reject', or 'review' — advisory only, human decides"
    )
    recommended_service: str = Field(
        description="Best-fit service key from AGENCY_CONFIG['services'], e.g. 'website_modernization'"
    )
    pain_point: str = Field(
        max_length=300,
        description="One-sentence pain point that the recommended service solves for THIS company",
    )
    pitch_angle: str = Field(
        max_length=500,
        description="Personalised one-liner pitch (used as email hook later)",
    )


# ── ICP definition (driven by agency_config) ─────────────────────────────────

_icp = AGENCY_CONFIG["icp"]
DEFAULT_ICP = {
    "target_industries": _icp["industries"],
    "target_regions": _icp["regions"],
    "company_size": _icp["employee_range"],
    "decision_maker_titles": _icp["decision_maker_titles"],
    "disqualifiers": _icp["disqualifiers"],
    "services_we_sell": list(AGENCY_CONFIG["services"].keys()),
    "service_signals": {
        k: v["signals"] for k, v in AGENCY_CONFIG["services"].items()
    },
}

SCORING_PROMPT = """\
You are an ICP scoring engine for a US-based digital agency.

{agency_context}

## ICP Definition
{icp_json}

## Lead Data
{lead_json}

## Scoring Guidelines
- 80-100: Perfect fit — approve immediately
- 60-79:  Good fit — likely approve
- 40-59:  Uncertain — needs human review
- 20-39:  Poor fit — likely reject
- 0-19:   Disqualified — reject

You MUST also pick the single best-fit service from the services list above
and write a one-sentence pain_point and a personalised pitch_angle.
If no service fits, set recommended_service to 'none'.
"""


# ── Scoring function ─────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=15),
    retry=retry_if_exception_type(Exception),
)
def score_lead(lead: dict, icp: dict | None = None) -> ICPScore:
    """
    Score a single lead against the ICP using Gemini 2.0 Flash.

    Args:
        lead: Lead record from DB (dict with company_name, website, etc.)
        icp: ICP definition dict. Uses DEFAULT_ICP if None.

    Returns:
        ICPScore with score, reasoning, and recommendation.
    """
    icp = icp or DEFAULT_ICP

    # Sanitize lead data for prompt (remove internal fields)
    safe_lead = {
        "company_name": lead.get("company_name", "Unknown"),
        "website": lead.get("website", "N/A"),
        "contact_email": "provided" if lead.get("contact_email") else "not found",
        "contact_name": lead.get("contact_name", "N/A"),
        "city": lead.get("city", "N/A"),
        "category": lead.get("category", "N/A"),
        "kvk_validated": lead.get("kvk_validated", False),
    }

    prompt = SCORING_PROMPT.format(
        agency_context=agency_prompt_snippet(),
        icp_json=json.dumps(icp, indent=2),
        lead_json=json.dumps(safe_lead, indent=2),
    )

    result = gemini_client.chat.completions.create(
        response_model=ICPScore,
        model="gemini-2.0-flash",
        messages=[{"role": "user", "content": prompt}],
    )

    return result


# ── Batch scoring ────────────────────────────────────────────────────────────

def score_leads_batch(
    conn,
    lead_ids: list[str],
    icp: dict | None = None,
) -> list[dict]:
    """
    Score multiple leads and update the database.

    Returns list of {lead_id, score, recommended_action} dicts.
    """
    results = []

    for lead_id in lead_ids:
        # Fetch lead from DB
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, company_name, website, contact_email,
                          contact_name, kvk_validated
                   FROM leads WHERE id = %s""",
                (lead_id,),
            )
            row = cur.fetchone()
        conn.commit()

        if not row:
            log.warning(f"Lead {lead_id} not found — skipping")
            continue

        lead = {
            "id": str(row[0]),
            "company_name": row[1],
            "website": row[2],
            "contact_email": row[3],
            "contact_name": row[4],
            "kvk_validated": row[5],
        }

        try:
            icp_score = score_lead(lead, icp)

            # Update lead in DB
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE leads
                       SET icp_score = %s, icp_reasoning = %s,
                           recommended_service = %s, pain_point = %s,
                           pitch_angle = %s, status = 'scored'
                       WHERE id = %s""",
                    (
                        icp_score.score,
                        icp_score.reasoning,
                        icp_score.recommended_service,
                        icp_score.pain_point,
                        icp_score.pitch_angle,
                        lead_id,
                    ),
                )
            conn.commit()

            results.append({
                "lead_id": lead_id,
                "score": icp_score.score,
                "reasoning": icp_score.reasoning,
                "recommended_action": icp_score.recommended_action,
                "red_flags": icp_score.red_flags,
            })

            log.info(
                f"Lead {lead_id} scored {icp_score.score}/100 "
                f"→ {icp_score.recommended_action}"
            )

        except Exception as e:
            conn.rollback()
            log.error(f"Failed to score lead {lead_id}: {e}")
            results.append({
                "lead_id": lead_id,
                "score": -1,
                "reasoning": f"Scoring error: {str(e)[:200]}",
                "recommended_action": "review",
                "red_flags": ["scoring_failed"],
            })

    return results


# ── Entry point for worker_core.execute_job ──────────────────────────────────

def run_lead_scoring(conn, job: dict) -> float:
    """
    Execute a lead_score job.

    Payload format:
        {"lead_ids": ["uuid1", "uuid2", ...], "icp": {...} (optional)}

    Returns:
        Approximate API cost in USD.
    """
    payload = job.get("payload", {})
    lead_ids = payload.get("lead_ids", [])
    icp = payload.get("icp")

    if not lead_ids:
        log.warning(f"lead_score job {job['id']} has no lead_ids")
        return 0.0

    results = score_leads_batch(conn, lead_ids, icp)

    # Queue Gate 1 Telegram notifications for high-scoring leads
    for r in results:
        if r["score"] >= 40:  # Worth showing to human
            # Fetch full lead for Telegram message
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, company_name, website, contact_email,
                              icp_score, icp_reasoning
                       FROM leads WHERE id = %s""",
                    (r["lead_id"],),
                )
                row = cur.fetchone()
            conn.commit()

            if row:
                from telegram_bot import send_lead_approval
                import asyncio

                lead_msg = {
                    "id": str(row[0]),
                    "company_name": row[1],
                    "website": row[2],
                    "contact_email": row[3],
                    "icp_score": row[4],
                    "icp_reasoning": row[5],
                }
                asyncio.run(send_lead_approval(lead_msg))

    # Approximate cost: Gemini 2.0 Flash is very cheap
    cost = len(lead_ids) * 0.001  # ~$0.001 per scoring call
    log.info(
        f"Scored {len(results)} leads. "
        f"Approx cost: ${cost:.4f}"
    )

    # ── Auto-queue pitch_select for leads that scored >= 40 ──────────────
    qualified_ids = [r["lead_id"] for r in results if r["score"] >= 40]
    if qualified_ids:
        import json as _json
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO jobs (job_type, payload, status)
                   VALUES ('pitch_select', %s, 'pending')""",
                (_json.dumps({"lead_ids": qualified_ids}),),
            )
        conn.commit()
        log.info(f"Queued pitch_select job for {len(qualified_ids)} leads")

    return cost

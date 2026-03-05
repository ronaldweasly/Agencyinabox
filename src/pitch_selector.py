"""
pitch_selector.py — Given a scored lead, decide WHICH service to pitch
and HOW to frame the first cold-email hook.

Called automatically after lead_scorer writes recommended_service.
Uses Gemini 2.0 Flash to generate a hyper-personalised pitch.
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

gemini_client = from_genai(
    client=genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "")),
    mode=Mode.GENAI_TOOLS,
)


# ── Output schema ────────────────────────────────────────────────────────────

class PitchDecision(BaseModel):
    """What to pitch and how."""
    service_key: str = Field(description="Key from AGENCY_CONFIG['services']")
    headline: str = Field(max_length=120, description="Email subject line")
    hook: str = Field(max_length=300, description="First paragraph of the cold email")
    pain_point: str = Field(max_length=200, description="The pain this solves for THEM")
    proof_point: str = Field(max_length=200, description="Stat or case-study snippet")
    cta: str = Field(max_length=100, description="Call-to-action sentence")
    confidence: int = Field(ge=0, le=100, description="How well this pitch fits the lead")


PITCH_PROMPT = """\
{agency_context}

## Lead
{lead_json}

## Scorer said
recommended_service: {rec_service}
pain_point: {pain}
pitch_angle: {angle}

Pick the best service and write a *cold-email hook* that:
1. Opens with a specific observation about their business (NOT generic).
2. Ties the observation to a dollar-impact pain point.
3. Offers a concrete next step (15-min call, free audit, etc.).

Keep it under 80 words total. No fluff.
"""


# ── Core function ────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=15),
    retry=retry_if_exception_type(Exception),
)
def select_pitch(lead: dict) -> PitchDecision:
    """Generate a PitchDecision for one lead."""
    prompt = PITCH_PROMPT.format(
        agency_context=agency_prompt_snippet(),
        lead_json=json.dumps(
            {k: lead.get(k) for k in
             ("company_name", "website", "category", "city",
              "icp_score", "recommended_service", "pain_point", "pitch_angle")},
            indent=2,
        ),
        rec_service=lead.get("recommended_service", "unknown"),
        pain=lead.get("pain_point", ""),
        angle=lead.get("pitch_angle", ""),
    )

    return gemini_client.chat.completions.create(
        response_model=PitchDecision,
        model="gemini-2.0-flash",
        messages=[{"role": "user", "content": prompt}],
    )


# ── Entry point for worker_core ──────────────────────────────────────────────

def run_pitch_select(conn, job: dict) -> float:
    """Execute a pitch_select job.

    Payload: {"lead_ids": ["uuid1", ...]}
    """
    payload = job.get("payload", {})
    lead_ids = payload.get("lead_ids", [])
    if not lead_ids:
        log.warning(f"pitch_select job {job['id']} has no lead_ids")
        return 0.0

    for lead_id in lead_ids:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, company_name, website, category, city,
                          icp_score, recommended_service, pain_point, pitch_angle
                   FROM leads WHERE id = %s""",
                (lead_id,),
            )
            row = cur.fetchone()
        conn.commit()

        if not row:
            log.warning(f"Lead {lead_id} not found — skipping pitch")
            continue

        lead = dict(zip(
            ("id", "company_name", "website", "category", "city",
             "icp_score", "recommended_service", "pain_point", "pitch_angle"),
            (str(row[0]), *row[1:]),
        ))

        try:
            decision = select_pitch(lead)

            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE leads
                       SET recommended_service = %s,
                           pain_point = %s,
                           pitch_angle = %s
                       WHERE id = %s""",
                    (
                        decision.service_key,
                        decision.pain_point,
                        decision.hook,
                        lead_id,
                    ),
                )
            conn.commit()

            log.info(
                f"Pitch for {lead_id}: {decision.service_key} "
                f"(confidence {decision.confidence}%)"
            )
        except Exception as e:
            conn.rollback()
            log.error(f"Pitch selection failed for {lead_id}: {e}")

    return len(lead_ids) * 0.001

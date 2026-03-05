"""
ai_scoring_worker.py — Celery worker for the AI scoring queue.
Pulls companies from ai_scoring_queue, calls Claude API,
stores 8-dimension scores in ai_scores table.
"""
from __future__ import annotations

import json
import logging
import os

import anthropic
import psycopg2

from src.queue_manager import ApiRateLimiter, celery_app

log = logging.getLogger(__name__)

_claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

_SYSTEM_PROMPT = """\
You are an expert B2B sales intelligence analyst specialising in digital
transformation opportunities. Analyse the provided company data and return
ONLY a valid JSON object — no markdown, no prose, no code fences.

Return this exact structure (all fields required):
{
  "website_modernity":      <int 0-100>,
  "tech_debt_signal":       <int 0-100>,
  "automation_opportunity": <int 0-100>,
  "growth_signal":          <int 0-100>,
  "digital_gap":            <int 0-100>,
  "icp_fit":                <int 0-100>,
  "company_maturity":       <int 0-100>,
  "engagement_readiness":   <int 0-100>,
  "composite_score":        <int 0-100>,
  "score_tier":             "hot" | "warm" | "cold",
  "recommended_service":    "<string>",
  "reasoning_summary":      "<2-3 sentence string>",
  "email_hook":             "<string — personalised cold email opener>",
  "key_signals": [
    {"signal": "<string>", "direction": "positive" | "negative", "weight": <float 0-1>}
  ]
}

Scoring bands: hot >= 70, warm 50-69, cold < 50.
Higher score = stronger buying signal.
"""

_USER_TEMPLATE = """\
Analyse this company for digital transformation opportunity:

COMPANY:   {name}
DOMAIN:    {domain}
INDUSTRY:  {industry}  |  EMPLOYEES: {employees}  |  FOUNDED: {founded}
LOCATION:  {city}, {state}

TECHNOLOGY:
  CMS/Platform : {cms}
  Tech Stack   : {tech_stack}
  PageSpeed    : {pagespeed}/100

GROWTH SIGNALS:
  Hiring       : {is_hiring} ({job_count} open roles)
  Advertising  : {is_advertising}
  Funding      : {funding}

Provide scoring now.
"""


@celery_app.task(
    name="src.workers.ai_scoring_worker.score_company",
    queue="ai_scoring_queue",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
)
def score_company(self, company_id: str, db_url: str) -> None:
    """
    Score a single company.

    Args:
        company_id: UUID of the company row in the companies table.
        db_url:     PostgreSQL connection string.
    """
    conn = psycopg2.connect(db_url)
    try:
        # ── 1. Fetch company ─────────────────────────────────────────────────
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, domain, industry, employee_count,
                       founded_year, city, state, tech_stack,
                       pagespeed_score, is_hiring, job_posting_count,
                       is_advertising, funding_stage
                FROM   companies
                WHERE  id = %s
                """,
                (company_id,),
            )
            row = cur.fetchone()

        if not row:
            log.warning("score_company: company %s not found — skipping", company_id)
            return

        (
            name, domain, industry, employees, founded, city, state,
            tech_stack, pagespeed, is_hiring, job_count,
            is_advertising, funding,
        ) = row

        tech = tech_stack or {}
        cms = tech.get("cms") or tech.get("CMS") or "unknown"

        # ── 2. Call Claude ───────────────────────────────────────────────────
        user_msg = _USER_TEMPLATE.format(
            name=name or "Unknown",
            domain=domain or "N/A",
            industry=industry or "Unknown",
            employees=employees or "Unknown",
            founded=founded or "Unknown",
            city=city or "Unknown",
            state=state or "Unknown",
            cms=cms,
            tech_stack=json.dumps(tech, ensure_ascii=False),
            pagespeed=pagespeed or "N/A",
            is_hiring=is_hiring,
            job_count=job_count or 0,
            is_advertising=is_advertising,
            funding=funding or "unknown",
        )

        with ApiRateLimiter("claude"):
            response = _claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )

        raw_text = response.content[0].text.strip()
        # Strip any accidental markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        result: dict = json.loads(raw_text)

        # ── 3. Persist score ─────────────────────────────────────────────────
        composite = int(result.get("composite_score", 0))
        tier = result.get("score_tier", "cold")
        qualified = composite >= 65
        tokens = response.usage.input_tokens + response.usage.output_tokens

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_scores (
                    company_id, website_modernity, tech_debt_signal,
                    automation_opp, growth_signal, company_maturity,
                    icp_fit, digital_gap, engagement_readiness,
                    composite_score, score_tier, reasoning_summary,
                    key_signals, recommended_service, email_hook,
                    model_version, tokens_used
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::jsonb, %s, %s, %s, %s
                )
                ON CONFLICT (company_id) DO UPDATE SET
                    composite_score    = EXCLUDED.composite_score,
                    score_tier         = EXCLUDED.score_tier,
                    reasoning_summary  = EXCLUDED.reasoning_summary,
                    email_hook         = EXCLUDED.email_hook,
                    tokens_used        = EXCLUDED.tokens_used,
                    scored_at          = NOW()
                """,
                (
                    company_id,
                    result.get("website_modernity"),
                    result.get("tech_debt_signal"),
                    result.get("automation_opportunity"),
                    result.get("growth_signal"),
                    result.get("company_maturity"),
                    result.get("icp_fit"),
                    result.get("digital_gap"),
                    result.get("engagement_readiness"),
                    composite,
                    tier,
                    result.get("reasoning_summary"),
                    json.dumps(result.get("key_signals", [])),
                    result.get("recommended_service"),
                    result.get("email_hook"),
                    "claude-sonnet-4-6",
                    tokens,
                ),
            )
            cur.execute(
                """
                UPDATE companies
                SET    ai_score           = %s,
                       qualified          = %s,
                       qualification_tier = %s
                WHERE  id = %s
                """,
                (composite, qualified, tier, company_id),
            )
        conn.commit()
        log.info("Scored %s: %d/100 (%s)", name, composite, tier)

    except json.JSONDecodeError as exc:
        conn.rollback()
        log.error("Claude returned invalid JSON for company %s: %s", company_id, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        conn.rollback()
        log.error("score_company failed for %s: %s", company_id, exc)
        raise self.retry(exc=exc)
    finally:
        conn.close()

"""
lead_pipeline.py — Orchestrates the full lead-to-revenue pipeline.

Pipeline stages:
  1. DISCOVERY  — Scrape Google Maps → enrich via Apollo/AnyMail → store
  2. KVK        — Validate against Dutch Chamber of Commerce
  3. SCORING    — Gemini 2.0 Flash ICP scoring (0-100)
  4. GATE 1     — Telegram approval for high-scoring leads
  5. OUTREACH   — Add approved leads to Instantly.ai campaign
  6. REPLY      — Process replies via SDR handler → Gate 2
  7. QUALIFY    — Convert qualified leads to project briefs → Gate 3

This module creates jobs in the job queue for each stage.
The worker_core picks them up via SKIP LOCKED.
"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


# ── Stage 1: Discovery → Scoring pipeline ────────────────────────────────────

def run_discovery_pipeline(
    conn,
    queries: list[str],
    region: str = "NL",
    limit_per_query: int = 20,
    campaign_id: str | None = None,
) -> dict:
    """
    Run the full discovery → KvK → scoring pipeline synchronously.

    This is typically called from a scheduled job or manual trigger.
    Creates lead_score jobs for all newly discovered leads.

    Returns:
        Summary dict with counts.
    """
    from lead_discovery import run_discovery
    from kvk_validator import validate_lead, mark_lead_validated

    # Step 1: Discover leads
    log.info(f"Starting discovery: {len(queries)} queries, region={region}")
    new_lead_ids = run_discovery(conn, queries, region, limit_per_query)

    if not new_lead_ids:
        log.info("No new leads discovered")
        return {"discovered": 0, "kvk_validated": 0, "scoring_jobs": 0}

    # Step 2: KvK validation for each new lead
    kvk_validated = 0
    for lead_id in new_lead_ids:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT company_name, website, city FROM leads WHERE id = %s",
                    (lead_id,),
                )
                row = cur.fetchone()
            conn.commit()

            if not row:
                continue

            result = validate_lead(
                company_name=row[0] or "",
                website=row[1],
                city=row[2] if len(row) > 2 else None,
            )
            mark_lead_validated(conn, lead_id, result)
            if result["validated"]:
                kvk_validated += 1

        except Exception as e:
            log.error(f"KvK validation failed for lead {lead_id}: {e}")

    # Step 3: Create lead_score jobs in batches
    # Group leads into batches of 10 for efficiency
    batch_size = 10
    scoring_jobs = 0

    for i in range(0, len(new_lead_ids), batch_size):
        batch = new_lead_ids[i : i + batch_size]
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO jobs (job_type, payload)
                       VALUES ('lead_score', %s::jsonb)
                       RETURNING id::text""",
                    (json.dumps({"lead_ids": batch}),),
                )
                result = cur.fetchone()
            conn.commit()
            if result:
                scoring_jobs += 1
                log.info(f"Created lead_score job for {len(batch)} leads")
        except Exception as e:
            conn.rollback()
            log.error(f"Failed to create lead_score job: {e}")

    # Record discovery run
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO discovery_runs
                   (queries, region, total_scraped, inserted, enriched_count, completed_at)
                   VALUES (%s::jsonb, %s, %s, %s, %s, NOW())""",
                (
                    json.dumps(queries),
                    region,
                    len(new_lead_ids),
                    len(new_lead_ids),
                    len(new_lead_ids),
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning(f"Failed to record discovery run: {e}")

    summary = {
        "discovered": len(new_lead_ids),
        "kvk_validated": kvk_validated,
        "scoring_jobs": scoring_jobs,
    }
    log.info(f"Discovery pipeline complete: {summary}")
    return summary


# ── Stage 5: Send outreach for approved leads ────────────────────────────────

def send_approved_outreach(
    conn,
    campaign_id: str,
    limit: int = 50,
) -> dict:
    """
    Find all leads with status 'approved' and add them to an Instantly.ai campaign.

    Called after Gate 1 approvals accumulate.

    Returns:
        {"sent": int, "failed": int, "no_email": int}
    """
    from instantly_client import send_outreach

    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id::text FROM leads
                   WHERE status = 'approved'
                     AND contact_email IS NOT NULL
                   ORDER BY icp_score DESC NULLS LAST
                   LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to fetch approved leads: {e}")
        return {"sent": 0, "failed": 0, "no_email": 0}

    sent = 0
    failed = 0

    for row in rows:
        lead_id = row[0]
        try:
            success = send_outreach(conn, lead_id, campaign_id)
            if success:
                sent += 1
            else:
                failed += 1
        except Exception as e:
            log.error(f"Outreach failed for lead {lead_id}: {e}")
            failed += 1

    summary = {"sent": sent, "failed": failed}
    log.info(f"Outreach batch complete: {summary}")
    return summary


# ── Stage 7: Convert qualified lead to project ──────────────────────────────

def create_project_from_lead(
    conn,
    lead_id: str,
    deliverable: str,
    tech_stack: dict,
    acceptance_criteria: list[str],
    budget_cap: float = 50.00,
) -> str | None:
    """
    Convert a qualified lead into a project with budget and initial GSD job.

    Returns:
        Project UUID or None on failure.
    """
    try:
        with conn.cursor() as cur:
            # Create budget
            cur.execute(
                """INSERT INTO project_budgets (project_cap)
                   VALUES (%s) RETURNING project_id::text""",
                (budget_cap,),
            )
            budget_id = cur.fetchone()[0]

            # Create project
            cur.execute(
                """INSERT INTO projects
                   (lead_id, budget_id, deliverable, tech_stack,
                    acceptance_criteria, status)
                   VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, 'planning')
                   RETURNING id::text""",
                (
                    lead_id,
                    budget_id,
                    deliverable,
                    json.dumps(tech_stack),
                    json.dumps(acceptance_criteria),
                ),
            )
            project_id = cur.fetchone()[0]

            # Update lead status
            cur.execute(
                """UPDATE leads
                   SET status = 'qualified'
                   WHERE id = %s""",
                (lead_id,),
            )

        conn.commit()
        log.info(f"Created project {project_id} from lead {lead_id}")
        return project_id

    except Exception as e:
        conn.rollback()
        log.error(f"Failed to create project from lead {lead_id}: {e}")
        return None


def queue_gsd_job(
    conn,
    project_id: str,
    brief: dict,
    libraries: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
) -> str | None:
    """
    Queue a GSD task job for a project.

    Returns job UUID or None.
    """
    payload = {
        "brief": brief,
        "libraries": libraries or [],
        "acceptance_criteria": acceptance_criteria or [],
    }

    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO jobs (project_id, job_type, payload)
                   VALUES (%s, 'gsd_task', %s::jsonb)
                   RETURNING id::text""",
                (project_id, json.dumps(payload)),
            )
            result = cur.fetchone()
        conn.commit()

        job_id = result[0] if result else None
        if job_id:
            log.info(f"Queued GSD job {job_id} for project {project_id}")
        return job_id

    except Exception as e:
        conn.rollback()
        log.error(f"Failed to queue GSD job for project {project_id}: {e}")
        return None


# ── Scheduled discovery trigger ──────────────────────────────────────────────

DEFAULT_DISCOVERY_QUERIES = [
    "IT consultant Amsterdam",
    "Software development bureau Utrecht",
    "Digital agency Rotterdam",
    "Webshop developer Den Haag",
    "SaaS startup Eindhoven",
    "Marketing automation bureau Nederland",
    "E-commerce specialist Groningen",
    "Cloud consultant Arnhem",
]


def run_scheduled_discovery(conn) -> dict:
    """
    Called by a cron/scheduled job to run the standard discovery pipeline.
    Uses default queries targeting the Dutch market.
    """
    return run_discovery_pipeline(
        conn,
        queries=DEFAULT_DISCOVERY_QUERIES,
        region="NL",
        limit_per_query=15,
    )

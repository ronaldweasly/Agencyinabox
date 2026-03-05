#!/usr/bin/env python3
"""
demo.py — Runs the full Agency-in-a-Box pipeline against local Postgres
           with ALL external APIs mocked. No keys required.

Usage:
    python demo.py

Requires:
    docker compose -f docker-compose.dev.yml up -d   (Postgres on localhost:5432)

What it demonstrates:
    1. Lead Discovery   — Simulates scraping 8 Dutch B2B companies
    2. KvK Validation   — Simulates Dutch Chamber of Commerce lookup
    3. ICP Scoring       — Simulates Gemini scoring each lead 0–100
    4. Gate 1 Approval   — Auto-approves leads scoring ≥ 60
    5. Outreach          — Simulates adding approved leads to Instantly.ai campaign
    6. Inbound Reply     — Simulates a prospect replying
    7. SDR Reply Draft   — Simulates AI drafting a Dutch reply
    8. Gate 2 Approval   — Auto-approves the reply
    9. Project Creation  — Converts a qualified lead into a project + GSD job
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
import uuid

# ── Bootstrap ────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("demo")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:localdev@localhost:5432/agency"
)

# ── Fake data ────────────────────────────────────────────────────────────────

FAKE_LEADS = [
    {
        "company_name": "CloudNine Solutions BV",
        "website": "https://cloudnine.nl",
        "contact_email": "jan.devries@cloudnine.nl",
        "contact_name": "Jan de Vries",
        "city": "Amsterdam",
        "category": "IT Consulting",
    },
    {
        "company_name": "DigiCraft Agency",
        "website": "https://digicraft.nl",
        "contact_email": "lisa.bakker@digicraft.nl",
        "contact_name": "Lisa Bakker",
        "city": "Utrecht",
        "category": "Digital Marketing",
    },
    {
        "company_name": "Pixel Perfect BV",
        "website": "https://pixelperfect.nl",
        "contact_email": "mark.jansen@pixelperfect.nl",
        "contact_name": "Mark Jansen",
        "city": "Rotterdam",
        "category": "Web Development",
    },
    {
        "company_name": "DataFlow Consultancy",
        "website": "https://dataflow.nl",
        "contact_email": "anna.smit@dataflow.nl",
        "contact_name": "Anna Smit",
        "city": "Den Haag",
        "category": "Data Engineering",
    },
    {
        "company_name": "TechForge BV",
        "website": "https://techforge.nl",
        "contact_email": "pieter.mulder@techforge.nl",
        "contact_name": "Pieter Mulder",
        "city": "Eindhoven",
        "category": "SaaS Development",
    },
    {
        "company_name": "WebWinkel Experts",
        "website": "https://webwinkelexperts.nl",
        "contact_email": "sarah.groot@webwinkelexperts.nl",
        "contact_name": "Sarah de Groot",
        "city": "Groningen",
        "category": "E-commerce",
    },
    {
        "company_name": "Byte Brigade",
        "website": "https://bytebrigade.nl",
        "contact_email": "tom.visser@bytebrigade.nl",
        "contact_name": "Tom Visser",
        "city": "Arnhem",
        "category": "Cloud Infrastructure",
    },
    {
        "company_name": "Random Freelancer",
        "website": "https://some-random-site.com",
        "contact_email": None,
        "contact_name": None,
        "city": None,
        "category": "Unknown",
    },
]

FAKE_ICP_SCORES = {
    "CloudNine Solutions BV":  {"score": 92, "reasoning": "Perfect ICP fit — IT consulting in Amsterdam, .nl domain, clear B2B services, decision-maker email available. Strong KvK validation."},
    "DigiCraft Agency":        {"score": 78, "reasoning": "Good fit — digital marketing agency in Utrecht, Dutch entity. Could use automation tools for their clients."},
    "Pixel Perfect BV":        {"score": 85, "reasoning": "Strong fit — web development BV in Rotterdam, likely needs build automation. KvK validated."},
    "DataFlow Consultancy":    {"score": 70, "reasoning": "Decent fit — data engineering consultancy, may need pipeline automation. Den Haag location."},
    "TechForge BV":            {"score": 88, "reasoning": "Excellent fit — SaaS dev in Eindhoven tech hub, actively building products. High automation potential."},
    "WebWinkel Experts":       {"score": 65, "reasoning": "Moderate fit — e-commerce specialist, could benefit from workflow automation. Regional player."},
    "Byte Brigade":            {"score": 74, "reasoning": "Good fit — cloud infrastructure provider, strong DevOps alignment. Arnhem based."},
    "Random Freelancer":       {"score": 15, "reasoning": "Poor fit — no .nl domain, no contact info, not a Dutch entity. Likely spam or irrelevant."},
}

FAKE_REPLY = """Hoi,

Bedankt voor je bericht. We zijn inderdaad op zoek naar manieren om onze development workflow te automatiseren. 

Kunnen we volgende week een kort gesprek plannen? Dinsdag of woensdag zou goed uitkomen.

Met vriendelijke groet,
Jan de Vries
CloudNine Solutions BV"""

FAKE_SDR_DRAFT = """Hoi Jan,

Wat leuk om van je te horen! Automatisering van de development workflow is precies waar wij ons op focussen.

Dinsdag om 14:00 zou perfect zijn. Ik stuur een Google Meet link mee. In het gesprek laat ik graag zien hoe we voor vergelijkbare IT-consultancies 40% tijdsbesparing realiseren op hun build-en-deploy proces.

Spreek je dinsdag!

Met vriendelijke groet,
Agency Bot"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_conn():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def domain_hash(domain: str) -> str:
    pepper = "demo-pepper-not-for-production"
    return hashlib.sha256(f"{pepper}:{domain}".encode()).hexdigest()


def banner(text: str) -> None:
    width = 70
    print()
    print("═" * width)
    print(f"  {text}")
    print("═" * width)


def step(text: str) -> None:
    print(f"\n  → {text}")


def ok(text: str) -> None:
    print(f"    ✓ {text}")


def info(text: str) -> None:
    print(f"    • {text}")


def warn(text: str) -> None:
    print(f"    ⚠ {text}")


# ── Demo stages ──────────────────────────────────────────────────────────────

def stage_1_discovery(conn) -> list[str]:
    """Insert fake leads into the database — simulates Outscraper + Apollo enrichment."""
    banner("STAGE 1: Lead Discovery (Outscraper → Apollo → AnyMail)")
    step("Scraping Google Maps for Dutch B2B companies...")
    time.sleep(0.5)

    lead_ids = []
    for lead in FAKE_LEADS:
        domain = lead["website"].replace("https://", "").replace("http://", "").rstrip("/")
        dh = domain_hash(domain)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO leads
                       (domain_hash, company_name, website, contact_email,
                        contact_name, city, category, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'new')
                       ON CONFLICT (domain_hash) DO NOTHING
                       RETURNING id::text""",
                    (dh, lead["company_name"], lead["website"],
                     lead["contact_email"], lead["contact_name"],
                     lead["city"], lead["category"]),
                )
                row = cur.fetchone()
            conn.commit()

            if row:
                lead_ids.append(row[0])
                ok(f"{lead['company_name']:30s}  {lead['city'] or '?':15s}  {lead['contact_email'] or '(no email)'}")
            else:
                warn(f"{lead['company_name']} — already exists (dedup)")
        except Exception as e:
            conn.rollback()
            warn(f"Failed to insert {lead['company_name']}: {e}")

    info(f"Discovered {len(lead_ids)} new leads")
    return lead_ids


def stage_2_kvk(conn, lead_ids: list[str]) -> int:
    """Simulate KvK validation."""
    banner("STAGE 2: KvK Validation (Dutch Chamber of Commerce)")
    step("Validating companies against KvK registry...")
    time.sleep(0.3)

    validated = 0
    for lid in lead_ids:
        with conn.cursor() as cur:
            cur.execute("SELECT company_name, website FROM leads WHERE id = %s", (lid,))
            row = cur.fetchone()
        conn.commit()

        if not row:
            continue

        name, website = row
        # Simulate: .nl domains from known companies pass KvK
        is_valid = website and ".nl" in website and name != "Random Freelancer"
        kvk_number = f"NL{hash(name) % 90000000 + 10000000}" if is_valid else None

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE leads SET kvk_validated = %s WHERE id = %s",
                (is_valid, lid),
            )
        conn.commit()

        if is_valid:
            validated += 1
            ok(f"{name:30s}  KvK: {kvk_number}  ✓ Validated")
        else:
            warn(f"{name:30s}  ✗ Not found in KvK registry")

    info(f"Validated {validated}/{len(lead_ids)} leads")
    return validated


def stage_3_scoring(conn, lead_ids: list[str]) -> list[dict]:
    """Simulate Gemini ICP scoring."""
    banner("STAGE 3: ICP Scoring (Gemini 2.0 Flash)")
    step("Scoring leads against Ideal Customer Profile...")
    time.sleep(0.5)

    scored = []
    for lid in lead_ids:
        with conn.cursor() as cur:
            cur.execute("SELECT company_name FROM leads WHERE id = %s", (lid,))
            row = cur.fetchone()
        conn.commit()

        if not row:
            continue

        name = row[0]
        score_data = FAKE_ICP_SCORES.get(name, {"score": 30, "reasoning": "Unknown company"})
        score = score_data["score"]
        reasoning = score_data["reasoning"]

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE leads SET icp_score = %s, icp_reasoning = %s WHERE id = %s",
                (score, reasoning, lid),
            )
        conn.commit()

        scored.append({"id": lid, "name": name, "score": score})

        bar = "█" * (score // 5) + "░" * (20 - score // 5)
        status = "🟢 APPROVE" if score >= 60 else "🔴 REJECT"
        ok(f"{name:30s}  [{bar}] {score:3d}/100  {status}")
        info(f"  {reasoning[:80]}")

    return scored


def stage_4_gate1(conn, scored: list[dict]) -> list[str]:
    """Simulate Telegram Gate 1 — auto-approve leads ≥ 60."""
    banner("STAGE 4: Gate 1 — Telegram Approval")
    step("Sending high-scoring leads to Telegram for approval...")
    time.sleep(0.3)

    approved_ids = []
    for s in scored:
        if s["score"] >= 60:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE leads SET status = 'approved' WHERE id = %s",
                    (s["id"],),
                )
            conn.commit()
            approved_ids.append(s["id"])
            ok(f"📱 {s['name']:30s}  Score {s['score']}  → APPROVED by @operator")
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE leads SET status = 'rejected' WHERE id = %s",
                    (s["id"],),
                )
            conn.commit()
            info(f"   {s['name']:30s}  Score {s['score']}  → auto-rejected (below threshold)")

    info(f"Gate 1 result: {len(approved_ids)} approved, {len(scored) - len(approved_ids)} rejected")
    return approved_ids


def stage_5_outreach(conn, approved_ids: list[str]) -> str:
    """Simulate Instantly.ai outreach campaign."""
    banner("STAGE 5: Outreach (Instantly.ai Cold Email)")
    step("Adding approved leads to email campaign...")
    time.sleep(0.3)

    campaign_id = f"camp_{uuid.uuid4().hex[:12]}"
    info(f"Campaign: {campaign_id}")

    for lid in approved_ids:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT company_name, contact_email FROM leads WHERE id = %s",
                (lid,),
            )
            row = cur.fetchone()
        conn.commit()

        if not row or not row[1]:
            warn(f"Lead {lid} — no email, skipped")
            continue

        name, email = row
        # Record outreach
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO outreach_campaigns (lead_id, campaign_id, status)
                   VALUES (%s, %s, 'active')
                   ON CONFLICT (lead_id, campaign_id) DO NOTHING""",
                (lid, campaign_id),
            )
            cur.execute(
                "UPDATE leads SET status = 'contacted', last_contact_date = NOW() WHERE id = %s",
                (lid,),
            )
        conn.commit()

        ok(f"📧 {name:30s}  → {email}")

    info(f"Campaign {campaign_id} launched with {len(approved_ids)} leads")
    return campaign_id


def stage_6_inbound_reply(conn, lead_id: str) -> str:
    """Simulate receiving a reply from a prospect."""
    banner("STAGE 6: Inbound Reply (Instantly.ai Webhook)")

    with conn.cursor() as cur:
        cur.execute("SELECT company_name, contact_name FROM leads WHERE id = %s", (lead_id,))
        row = cur.fetchone()
    conn.commit()

    company, contact = row if row else ("Unknown", "Unknown")

    step(f"Received reply from {contact} at {company}...")
    time.sleep(0.3)

    # Store inbound reply
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO reply_threads (lead_id, direction, body, status)
               VALUES (%s, 'inbound', %s, 'received')
               RETURNING id::text""",
            (lead_id, FAKE_REPLY),
        )
        reply_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE leads SET status = 'replied' WHERE id = %s",
            (lead_id,),
        )
    conn.commit()

    print()
    print("    ┌──────────────────────────────────────────────────────────────┐")
    for line in FAKE_REPLY.strip().split("\n"):
        print(f"    │  {line:60s}│")
    print("    └──────────────────────────────────────────────────────────────┘")

    ok(f"Reply stored (thread {reply_id[:8]}...)")
    return reply_id


def stage_7_sdr_reply(conn, lead_id: str) -> str:
    """Simulate AI SDR drafting a reply."""
    banner("STAGE 7: SDR Reply Draft (Gemini 2.0 Flash)")
    step("AI drafting Dutch B2B reply based on conversation context...")
    time.sleep(0.7)

    # Store outbound draft
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO reply_threads
               (lead_id, direction, body, status)
               VALUES (%s, 'outbound', %s, 'pending_approval')
               RETURNING id::text""",
            (lead_id, FAKE_SDR_DRAFT),
        )
        draft_id = cur.fetchone()[0]
    conn.commit()

    print()
    print("    ┌── AI Draft ───────────────────────────────────────────────────┐")
    for line in FAKE_SDR_DRAFT.strip().split("\n"):
        print(f"    │  {line:60s}│")
    print("    └──────────────────────────────────────────────────────────────┘")
    info("Confidence: 0.91  |  Stage: scheduling  |  Tone: professional")
    ok(f"Draft stored (id {draft_id[:8]}...) — awaiting Gate 2 approval")
    return draft_id


def stage_8_gate2(conn, draft_id: str) -> None:
    """Simulate Telegram Gate 2 — human approves the reply."""
    banner("STAGE 8: Gate 2 — Reply Approval")
    step("Sending draft to Telegram for human review...")
    time.sleep(0.3)

    with conn.cursor() as cur:
        cur.execute(
            """UPDATE reply_threads
               SET status = 'approved', approved_at = NOW(), approved_by = 'telegram:operator'
               WHERE id = %s""",
            (draft_id,),
        )
    conn.commit()

    ok("📱 Reply APPROVED by @operator")
    info("Reply would now be sent via Instantly.ai API")

    # Mark as sent
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE reply_threads SET status = 'sent' WHERE id = %s",
            (draft_id,),
        )
    conn.commit()
    ok("📤 Reply sent to prospect")


def stage_9_project(conn, lead_id: str) -> None:
    """Create a project from a qualified lead and queue a GSD job."""
    banner("STAGE 9: Lead → Project Conversion (Gate 3)")
    step("Converting qualified lead into development project...")
    time.sleep(0.3)

    with conn.cursor() as cur:
        cur.execute("SELECT company_name FROM leads WHERE id = %s", (lead_id,))
        name = cur.fetchone()[0]
    conn.commit()

    # Create budget
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO project_budgets (project_cap) VALUES (50.00) RETURNING project_id::text",
        )
        budget_id = cur.fetchone()[0]
    conn.commit()

    # Create project
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO projects
               (lead_id, budget_id, deliverable, tech_stack, acceptance_criteria, status)
               VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, 'planning')
               RETURNING id::text""",
            (
                lead_id,
                budget_id,
                "Automated CI/CD pipeline with GitHub Actions",
                json.dumps({"language": "Python", "framework": "FastAPI", "ci": "GitHub Actions"}),
                json.dumps(["All tests pass", "Coverage > 90%", "Deploy to staging on merge"]),
            ),
        )
        project_id = cur.fetchone()[0]
    conn.commit()

    ok(f"Project created: {project_id[:8]}...")
    info(f"Client: {name}")
    info("Deliverable: Automated CI/CD pipeline with GitHub Actions")
    info("Budget cap: $50.00")

    # Queue GSD job
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO jobs (project_id, job_type, payload)
               VALUES (%s, 'gsd_task', %s::jsonb)
               RETURNING id::text""",
            (
                project_id,
                json.dumps({
                    "brief": {
                        "description": "Build a CI/CD pipeline using GitHub Actions for a FastAPI app",
                        "requirements": [
                            "Lint with ruff",
                            "Type-check with mypy",
                            "Run pytest with coverage",
                            "Deploy to Fly.io on merge to main",
                        ],
                    },
                    "libraries": ["fastapi", "pytest", "ruff", "mypy"],
                    "acceptance_criteria": ["All tests pass", "Coverage > 90%"],
                }),
            ),
        )
        job_id = cur.fetchone()[0]
    conn.commit()

    ok(f"GSD job queued: {job_id[:8]}...")
    info("Job type: gsd_task")
    info("→ Worker would now: RESEARCH → IMPLEMENT → QA → CRITIC → PR → Gate 4")

    # Update lead
    with conn.cursor() as cur:
        cur.execute("UPDATE leads SET status = 'qualified' WHERE id = %s", (lead_id,))
    conn.commit()


def print_summary(conn) -> None:
    """Print final database state."""
    banner("DEMO COMPLETE — Database Summary")

    with conn.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM leads GROUP BY status ORDER BY status")
        rows = cur.fetchall()
    conn.commit()
    step("Lead status breakdown:")
    for status, count in rows:
        ok(f"{status:20s}  {count}")

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM outreach_campaigns")
        campaigns = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM reply_threads")
        replies = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM projects")
        projects = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM jobs")
        jobs = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM discovery_runs")
        discovery_runs = cur.fetchone()[0]
    conn.commit()

    step("Pipeline metrics:")
    ok(f"Outreach campaigns:  {campaigns}")
    ok(f"Reply threads:       {replies}")
    ok(f"Projects created:    {projects}")
    ok(f"Jobs queued:         {jobs}")

    # Record discovery run
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO discovery_runs
               (queries, region, total_scraped, inserted, enriched_count, completed_at)
               VALUES (%s::jsonb, 'NL', %s, %s, %s, NOW())""",
            (json.dumps(["demo run"]), len(FAKE_LEADS), len(FAKE_LEADS), len(FAKE_LEADS)),
        )
    conn.commit()

    print()
    print("  🎉 Full lead-to-revenue pipeline demonstrated successfully!")
    print()
    print("  To run with REAL APIs, fill in your keys in .env and run:")
    print("    cd src && python -m src        (worker)")
    print("    uvicorn dmz.main:app --port 8001  (DMZ gateway)")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print("  ╔══════════════════════════════════════════════════════════════════╗")
    print("  ║          AGENCY-IN-A-BOX  —  DEMO MODE (no API keys)           ║")
    print("  ║                                                                 ║")
    print("  ║  Full lead-to-revenue pipeline against local PostgreSQL.        ║")
    print("  ║  All external APIs (Gemini, Anthropic, Telegram, GitHub,        ║")
    print("  ║  Fly.io, Outscraper, Apollo, KvK, Instantly) are simulated.     ║")
    print("  ╚══════════════════════════════════════════════════════════════════╝")

    conn = get_conn()

    try:
        # Clean previous demo data
        step("Cleaning previous demo data...")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs_audit")
            cur.execute("DELETE FROM alerts")
            cur.execute("DELETE FROM jobs")
            cur.execute("DELETE FROM projects")
            cur.execute("DELETE FROM project_budgets")
            cur.execute("DELETE FROM reply_threads")
            cur.execute("DELETE FROM outreach_campaigns")
            cur.execute("DELETE FROM lead_status_log")
            cur.execute("DELETE FROM discovery_runs")
            cur.execute("DELETE FROM leads")
        conn.commit()
        ok("Database cleaned")

        # Run the pipeline
        lead_ids = stage_1_discovery(conn)
        stage_2_kvk(conn, lead_ids)
        scored = stage_3_scoring(conn, lead_ids)
        approved_ids = stage_4_gate1(conn, scored)

        if not approved_ids:
            warn("No leads approved — demo ends here")
            return

        campaign_id = stage_5_outreach(conn, approved_ids)

        # Pick the highest-scoring lead for reply simulation
        best_lead = max(scored, key=lambda x: x["score"])
        best_id = best_lead["id"]

        reply_id = stage_6_inbound_reply(conn, best_id)
        draft_id = stage_7_sdr_reply(conn, best_id)
        stage_8_gate2(conn, draft_id)
        stage_9_project(conn, best_id)

        print_summary(conn)

    except Exception as e:
        conn.rollback()
        log.error(f"Demo failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

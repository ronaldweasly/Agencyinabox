"""
gsd_executor.py — GSD Code Engine (Claude Sonnet executor)

Follows the RESEARCH → ARCH → IMPL → QA → DEPLOY pipeline.

Fixes applied from PROBLEMS.md:
  P-20: System prompt passed via messages list (not system= kwarg).
        instructor's from_anthropic may silently drop system= in some versions.
  P-21: Firecrawl API updated to v1 endpoint.
  P-23: Uses shared schemas from schemas.py (single source of truth).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import anthropic
import httpx
from instructor import from_anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from schemas import CodeOutput, ResearchBundle

log = logging.getLogger(__name__)

# ── Claude client (instructor-wrapped for Pydantic enforcement) ──────────────

claude_client = from_anthropic(
    anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
)


# ── PHASE 0: RESEARCH ───────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_live_docs(library: str) -> ResearchBundle:
    """
    Fetches live API docs via Firecrawl v1 and compiles research bundle.
    P-21 fix: Uses /v1/search endpoint (v0 is deprecated).
    """
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    if not firecrawl_key:
        log.warning("FIRECRAWL_API_KEY not set — returning empty research bundle")
        return ResearchBundle(
            library_name=library,
            version_pinned="unknown",
            docs_digest="Firecrawl not configured — manual research required",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    # P-21 fix: v1 endpoint
    search_url = "https://api.firecrawl.dev/v1/search"
    year = datetime.now().year

    queries = [
        f"{library} official API documentation {year}",
        f"{library} changelog breaking changes {year}",
        f"{library} python examples github",
    ]

    docs_text = ""
    with httpx.Client(timeout=30) as client:
        for q in queries:
            try:
                resp = client.post(
                    search_url,
                    headers={"Authorization": f"Bearer {firecrawl_key}"},
                    json={"query": q, "pageOptions": {"onlyMainContent": True}},
                )
                if resp.status_code == 200:
                    for result in resp.json().get("data", [])[:2]:
                        docs_text += result.get("content", "")[:2000] + "\n\n"
            except httpx.HTTPError as e:
                log.warning(f"Firecrawl search failed for query '{q}': {e}")
                continue

    if not docs_text.strip():
        return ResearchBundle(
            library_name=library,
            version_pinned="unknown",
            docs_digest="No documentation fetched — check Firecrawl quota",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    # Use Claude to extract structured research from raw docs
    # P-20 fix: system prompt in messages, not as system= kwarg
    bundle = claude_client.chat.completions.create(
        model="claude-sonnet-4-6",
        response_model=ResearchBundle,
        max_retries=2,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are a senior Python engineer researching a library.\n"
                    f"Extract a structured research bundle for '{library}' from the "
                    f"following documentation:\n\n{docs_text[:6000]}"
                ),
            }
        ],
    )
    bundle.retrieved_at = datetime.now(timezone.utc).isoformat()
    return bundle


def fetch_pypi_version(package: str) -> str:
    """Pin the latest stable version from PyPI."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"https://pypi.org/pypi/{package}/json")
            if resp.status_code == 200:
                return resp.json()["info"]["version"]
    except Exception as e:
        log.warning(f"PyPI lookup failed for {package}: {e}")
    return "unknown"


# ── PHASE 2: IMPLEMENTATION ─────────────────────────────────────────────────

IMPLEMENTATION_RULES = """\
You are a senior Python engineer. MANDATORY RULES — violation = rejection:

1. Write TESTS FIRST (TDD). Test file must be complete in test_code field.
2. Cite documentation source + version for every external API call.
   Format: # Source: {url}, retrieved {date}
3. Use ONLY pinned versions from the provided research_bundles.
4. Never use deprecated methods (check breaking_changes in research).
5. Max 30 lines per function. If exceeded, split into sub-functions.
6. Every function: docstring with purpose, args, returns, raises.
7. Flag every assumption: # ASSUMPTION: {description}
8. Output full_code and test_code as COMPLETE files. No diffs. No placeholders.
   No '...' or 'pass # TODO'. Every line must be real code.
9. requirements.txt must pin every dependency: package==X.Y.Z
10. Handle all external API errors: timeout, auth failure, rate limit, 5xx.
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=4, max=30),
    retry=retry_if_exception_type(Exception),
)
def generate_code(
    brief: dict,
    research_bundles: list[ResearchBundle],
) -> CodeOutput:
    """
    Phase 2: Generate complete implementation following TDD rules.
    P-20 fix: System prompt included as first user message, not system= kwarg.
    """
    research_context = json.dumps(
        [b.model_dump() for b in research_bundles], indent=2
    )

    # P-20 fix: Include rules directly in messages (not system= kwarg)
    output = claude_client.chat.completions.create(
        model="claude-sonnet-4-6",
        response_model=CodeOutput,
        max_retries=2,
        messages=[
            {
                "role": "user",
                "content": IMPLEMENTATION_RULES,
            },
            {
                "role": "user",
                "content": f"Research bundles:\n```json\n{research_context}\n```",
            },
            {
                "role": "user",
                "content": f"Project brief:\n```json\n{json.dumps(brief, indent=2)}\n```",
            },
            {
                "role": "user",
                "content": (
                    "Generate complete implementation following ALL rules above.\n"
                    "Write the test file FIRST, then the implementation to pass those tests."
                ),
            },
        ],
    )
    return output


# ── Pipeline orchestrator ────────────────────────────────────────────────────

def run_gsd_pipeline(conn, job: dict, heartbeat) -> float:
    """
    Execute the full GSD pipeline for a job.

    Returns the total API cost incurred.
    """
    payload = job.get("payload", {})
    project_id = str(job["project_id"])
    total_cost = 0.0  # Track actual spend

    # Phase 0: Research
    libraries = payload.get("libraries", [])
    research_bundles = []
    for lib in libraries:
        if heartbeat.should_abort:
            raise RuntimeError("Heartbeat dead during research phase")
        bundle = fetch_live_docs(lib)
        bundle.version_pinned = fetch_pypi_version(lib)
        research_bundles.append(bundle)
        total_cost += 0.01  # Approximate research cost

    # Store research in DB for audit trail
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE projects SET gsd_task_tree = gsd_task_tree || %s::jsonb,
                      updated_at = NOW()
               WHERE id = %s""",
            (
                json.dumps({"research": [b.model_dump() for b in research_bundles]}),
                project_id,
            ),
        )
    conn.commit()

    # Phase 2: Implementation
    if heartbeat.should_abort:
        raise RuntimeError("Heartbeat dead before implementation phase")

    brief = payload.get("brief", {})
    code_output = generate_code(brief, research_bundles)
    total_cost += 0.04  # Approximate Claude call cost

    # Phase 3: QA (delegated to Fly.io sandbox — see sandbox.py)
    if heartbeat.should_abort:
        raise RuntimeError("Heartbeat dead before QA phase")

    from sandbox import run_sandbox_qa
    qa_result = run_sandbox_qa(code_output, project_id)
    total_cost += 0.02  # Fly.io machine cost

    if qa_result.status != "passed":
        raise RuntimeError(
            f"QA failed: {qa_result.error or 'See QA report for details'}"
        )

    # Phase 3, Gate D: Critic Agent
    if heartbeat.should_abort:
        raise RuntimeError("Heartbeat dead before critic phase")

    from critic_agent import run_critic
    acceptance = payload.get("acceptance_criteria", [])
    critic_report = run_critic(code_output, qa_result.model_dump(), acceptance)
    total_cost += 0.01  # Gemini call cost

    if critic_report.verdict == "REJECTED":
        blockers = "; ".join(critic_report.blocker_issues)
        majors = "; ".join(critic_report.major_issues)
        raise RuntimeError(f"Critic rejected: blockers=[{blockers}] majors=[{majors}]")

    # Phase 4: Create GitHub PR and send Gate 4 Telegram message
    from pr_creator import run_pr_pipeline
    from telegram_bot import send_code_review
    import asyncio
    import os

    repo = payload.get("github_repo") or os.environ.get("GITHUB_REPO_DEFAULT", "agency-delivery")
    branch = f"gsd/{project_id[:8]}-{int(__import__('time').time())}"

    qa_summary = {
        "tests_passed": qa_result.tests_passed,
        "tests_total": qa_result.tests_total,
        "coverage_percent": qa_result.coverage_percent,
        "bandit_findings": qa_result.bandit_findings,
        "all_passed": qa_result.status == "passed",
        "critic_verdict": critic_report.verdict,
        "correctness": critic_report.correctness_score,
        "security": critic_report.security_score,
        "maintainability": critic_report.maintainability_score,
    }

    pr_result = run_pr_pipeline(
        conn, project_id, repo, branch,
        code_output, qa_summary, critic_report,
    )
    total_cost += 0.001  # GitHub API calls are free but minimal overhead

    # Send Gate 4 Telegram message for human review
    with conn.cursor() as cur:
        cur.execute(
            "SELECT deliverable, github_pr_number FROM projects WHERE id = %s",
            (project_id,),
        )
        row = cur.fetchone()

    project = {
        "id": project_id,
        "deliverable": row[0] if row else "N/A",
        "github_repo": repo,
        "github_pr_number": pr_result["pr_number"],
        "job_id": str(job.get("id", "")),
    }
    asyncio.run(send_code_review(project, pr_result["pr_url"], qa_summary))

    log.info(
        f"GSD pipeline complete for project {project_id}. "
        f"PR #{pr_result['pr_number']}, Critic: {critic_report.verdict}, "
        f"cost: ${total_cost:.4f}"
    )

    return total_cost

"""
critic_agent.py — Cross-model QA: Gemini reviews Claude's code.

Different model families catch different blind spots.
This is the final automated gate before code reaches Telegram approval.

Fixes applied from PROBLEMS.md:
  P-22: instructor's from_gemini API verified — using messages-based system prompt.
  P-23: Uses shared CriticReport from schemas.py (single source of truth).
"""
from __future__ import annotations

import json
import logging
import os

import google.genai as genai
from instructor import from_genai, Mode
from tenacity import retry, stop_after_attempt, wait_exponential

from schemas import CriticReport

log = logging.getLogger(__name__)

# ── Gemini client (instructor-wrapped for Pydantic enforcement) ──────────────

gemini_client = from_genai(
    client=genai.Client(api_key=os.environ["GEMINI_API_KEY"]),
    mode=Mode.GENAI_TOOLS,
)

CRITIC_SYSTEM = """\
You are a hostile senior code reviewer. Your ONLY job is to find problems.
You are NOT trying to be helpful to the author. You must REJECT code aggressively.

Rate each issue: BLOCKER (must fix) | MAJOR (should fix) | MINOR (nice to fix).

A BLOCKER exists if ANY of the following are true:
- Security vulnerability (SQL injection, path traversal, command injection, etc.)
- Incorrect API usage (wrong method, wrong parameters, wrong return type)
- Test coverage below 90% branch coverage
- Deprecated method used (check against research bundle breaking_changes)
- Undocumented assumption (missing # ASSUMPTION: comment)
- Any function exceeds 30 lines
- Missing error handling on any external API call (HTTP, DB, file I/O)
- Hardcoded secrets or credentials
- No input validation on user-facing functions

Auto-REJECT if: any BLOCKER exists, OR more than 2 MAJOR issues found.

Output ONLY valid JSON matching the CriticReport schema.
"""


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
def run_critic(
    code_output,  # CodeOutput from gsd_executor
    qa_results: dict,
    acceptance_criteria: list[str],
) -> CriticReport:
    """
    Runs Gemini as an adversarial reviewer on Claude's output.

    P-22 fix: System prompt passed via messages (not system= kwarg).
    Returns REJECTED if any BLOCKER or more than 2 MAJOR issues found.
    """
    review_input = {
        "code": code_output.full_code[:6000],  # Truncate to prevent context overflow
        "tests": code_output.test_code[:3000],
        "docs_cited": code_output.docs_cited,
        "assumptions": code_output.assumptions,
        "pytest_results": {
            k: v
            for k, v in qa_results.items()
            if k in ("status", "tests_passed", "tests_failed", "coverage_percent",
                      "ruff_issues", "mypy_issues", "bandit_findings")
        },
        "acceptance_criteria": acceptance_criteria,
    }

    # P-22 fix: system prompt in messages, not as system= kwarg
    report = gemini_client.chat.completions.create(
        response_model=CriticReport,
        max_retries=2,
        model="gemini-2.0-flash",
        messages=[
            {"role": "user", "content": CRITIC_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Review this code submission. Be adversarial.\n\n"
                    f"```json\n{json.dumps(review_input, indent=2)[:8000]}\n```"
                ),
            },
        ],
    )

    # Apply rejection rules deterministically (don't trust the model's verdict)
    if report.blocker_issues or len(report.major_issues) > 2:
        report.verdict = "REJECTED"
    else:
        report.verdict = "APPROVED"

    log.info(
        f"Critic verdict: {report.verdict} "
        f"(blockers={len(report.blocker_issues)}, "
        f"majors={len(report.major_issues)}, "
        f"minors={len(report.minor_issues)})"
    )

    return report

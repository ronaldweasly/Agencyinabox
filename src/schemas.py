"""
schemas.py — Single source of truth for all Pydantic models.

Fixes P-23: CriticReport was defined in two files with different fields.
All shared models live here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── GSD Research ──────────────────────────────────────────────────────

class ResearchBundle(BaseModel):
    """Output of Phase 0: research on a single library/API."""
    library_name: str
    version_pinned: str
    docs_digest: str = Field(max_length=4000, description="Max ~2000 tokens")
    breaking_changes: list[str] = Field(default_factory=list)
    cve_warnings: list[str] = Field(default_factory=list)
    retrieved_at: str = ""


# ── GSD Implementation ────────────────────────────────────────────────

class CodeOutput(BaseModel):
    """Output of Phase 2: Claude's complete implementation."""
    full_code: str = Field(description="Complete source file — no diffs, no placeholders")
    test_code: str = Field(description="Complete test file — written BEFORE implementation")
    requirements_txt: str = Field(description="Pinned dependencies, one per line")
    assumptions: list[str] = Field(default_factory=list)
    docs_cited: list[str] = Field(default_factory=list)


# ── Critic Review ─────────────────────────────────────────────────────

class CriticReport(BaseModel):
    """
    Output of Phase 3, Gate D: Gemini's adversarial review of Claude's code.
    Single canonical definition (fixes P-23).
    """
    verdict: str = Field(description="'APPROVED' or 'REJECTED'")
    blocker_issues: list[str] = Field(default_factory=list)
    major_issues: list[str] = Field(default_factory=list)
    minor_issues: list[str] = Field(default_factory=list)
    correctness_score: int = Field(ge=0, le=100)
    security_score: int = Field(ge=0, le=100)
    maintainability_score: int = Field(ge=0, le=100)
    docs_compliance: bool = False
    critic_notes: str = ""


# ── Sandbox QA Result ─────────────────────────────────────────────────

class SandboxResult(BaseModel):
    """Structured result from Fly.io sandbox execution."""
    status: str  # "passed", "failed", "fatal"
    pytest_exit_code: int = -1
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    coverage_percent: float = 0.0
    ruff_issues: int = 0
    mypy_issues: int = 0
    bandit_findings: int = 0
    error: str | None = None

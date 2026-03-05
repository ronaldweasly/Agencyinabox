"""
tests/test_schemas.py — Unit tests for all Pydantic models in schemas.py

Verifies field types, defaults, constraints, and JSON round-trips.
No external dependencies — only pydantic.
"""
from __future__ import annotations

import json
import unittest


class TestResearchBundle(unittest.TestCase):

    def test_minimal_construction(self):
        """ResearchBundle with only required fields."""
        from src.schemas import ResearchBundle

        rb = ResearchBundle(
            library_name="httpx",
            version_pinned="0.28.1",
            docs_digest="HTTP client for Python",
        )
        self.assertEqual(rb.library_name, "httpx")
        self.assertEqual(rb.version_pinned, "0.28.1")
        self.assertEqual(rb.breaking_changes, [])
        self.assertEqual(rb.cve_warnings, [])
        self.assertEqual(rb.retrieved_at, "")

    def test_docs_digest_max_length(self):
        """docs_digest accepts up to 4000 characters."""
        from src.schemas import ResearchBundle

        long_text = "x" * 4000
        rb = ResearchBundle(
            library_name="lib", version_pinned="1.0", docs_digest=long_text
        )
        self.assertEqual(len(rb.docs_digest), 4000)

    def test_json_round_trip(self):
        """model_dump() and model_validate() are inverse operations."""
        from src.schemas import ResearchBundle

        rb = ResearchBundle(
            library_name="psycopg2",
            version_pinned="2.9.9",
            docs_digest="Postgres adapter",
            breaking_changes=["Row factory API changed in 3.0"],
            retrieved_at="2026-03-05T00:00:00Z",
        )
        dumped = rb.model_dump()
        restored = ResearchBundle.model_validate(dumped)
        self.assertEqual(rb, restored)


class TestCodeOutput(unittest.TestCase):

    def test_all_fields_required(self):
        """Missing required fields raises ValidationError."""
        from pydantic import ValidationError
        from src.schemas import CodeOutput

        with self.assertRaises(ValidationError):
            CodeOutput(full_code="x")  # missing test_code, requirements_txt

    def test_full_construction(self):
        """All fields provided — model validates correctly."""
        from src.schemas import CodeOutput

        co = CodeOutput(
            full_code="def main(): pass",
            test_code="def test_main(): pass",
            requirements_txt="httpx==0.28.1",
            assumptions=["API is idempotent"],
            docs_cited=["https://www.python-httpx.org/"],
        )
        self.assertEqual(co.assumptions, ["API is idempotent"])
        self.assertEqual(co.docs_cited, ["https://www.python-httpx.org/"])


class TestCriticReport(unittest.TestCase):

    def test_score_bounds_enforced(self):
        """Scores outside [0, 100] raise ValidationError."""
        from pydantic import ValidationError
        from src.schemas import CriticReport

        with self.assertRaises(ValidationError):
            CriticReport(
                verdict="APPROVED",
                correctness_score=101,  # > 100
                security_score=50,
                maintainability_score=50,
            )

        with self.assertRaises(ValidationError):
            CriticReport(
                verdict="APPROVED",
                correctness_score=50,
                security_score=-1,  # < 0
                maintainability_score=50,
            )

    def test_default_lists_are_empty(self):
        """blocker_issues, major_issues, minor_issues default to []."""
        from src.schemas import CriticReport

        report = CriticReport(
            verdict="APPROVED",
            correctness_score=90,
            security_score=95,
            maintainability_score=85,
        )
        self.assertEqual(report.blocker_issues, [])
        self.assertEqual(report.major_issues, [])
        self.assertEqual(report.minor_issues, [])

    def test_rejected_verdict(self):
        """REJECTED verdict with blocker issues stores correctly."""
        from src.schemas import CriticReport

        report = CriticReport(
            verdict="REJECTED",
            blocker_issues=["SQL injection in query builder"],
            correctness_score=40,
            security_score=10,
            maintainability_score=60,
        )
        self.assertEqual(report.verdict, "REJECTED")
        self.assertEqual(len(report.blocker_issues), 1)


class TestSandboxResult(unittest.TestCase):

    def test_defaults(self):
        """SandboxResult with only status fills all defaults correctly."""
        from src.schemas import SandboxResult

        result = SandboxResult(status="passed")
        self.assertEqual(result.pytest_exit_code, -1)
        self.assertEqual(result.tests_passed, 0)
        self.assertEqual(result.coverage_percent, 0.0)
        self.assertIsNone(result.error)

    def test_fatal_with_error_message(self):
        """Fatal status with error message."""
        from src.schemas import SandboxResult

        result = SandboxResult(
            status="fatal", error="Sandbox timed out after 120s"
        )
        self.assertEqual(result.status, "fatal")
        self.assertEqual(result.error, "Sandbox timed out after 120s")


if __name__ == "__main__":
    unittest.main()

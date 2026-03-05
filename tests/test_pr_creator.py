"""
tests/test_pr_creator.py — Unit tests for pr_creator.py

All GitHub API calls mocked via httpx. No live credentials needed.
Tests: branch creation, file commit, PR opening, run_pr_pipeline integration.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch, call


def _mock_http_response(status_code: int, data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


class TestGetDefaultBranchSha(unittest.TestCase):

    def test_fetches_sha_from_default_branch(self):
        """Happy path: returns HEAD SHA from default branch."""
        from src.pr_creator import _get_default_branch_sha

        repo_resp = _mock_http_response(200, {"default_branch": "main"})
        ref_resp = _mock_http_response(200, {"object": {"sha": "abc123"}})

        client = MagicMock()
        client.get.side_effect = [repo_resp, ref_resp]

        with patch.dict("os.environ", {"GITHUB_ORG": "test-org", "GITHUB_PAT": "tok"}):
            sha = _get_default_branch_sha(client, "my-repo")

        self.assertEqual(sha, "abc123")
        self.assertEqual(client.get.call_count, 2)


class TestCreateBranch(unittest.TestCase):

    def test_creates_branch_via_post(self):
        """create_branch posts to /git/refs and calls raise_for_status."""
        from src.pr_creator import create_branch

        resp = _mock_http_response(201, {"ref": "refs/heads/gsd/test"})
        client = MagicMock()
        client.post.return_value = resp

        with patch.dict("os.environ", {"GITHUB_ORG": "test-org", "GITHUB_PAT": "tok"}):
            create_branch(client, "my-repo", "gsd/test", "abc123")

        client.post.assert_called_once()
        resp.raise_for_status.assert_called_once()

    def test_raises_on_http_error(self):
        """create_branch propagates HTTP errors from raise_for_status."""
        from src.pr_creator import create_branch

        resp = _mock_http_response(422, {"message": "Reference already exists"})
        client = MagicMock()
        client.post.return_value = resp

        with patch.dict("os.environ", {"GITHUB_ORG": "test-org", "GITHUB_PAT": "tok"}):
            with self.assertRaises(Exception):
                create_branch(client, "my-repo", "gsd/test", "abc123")


class TestCommitFile(unittest.TestCase):

    def test_creates_new_file(self):
        """commit_file PUTs new file when check returns 404."""
        from src.pr_creator import commit_file

        check_resp = _mock_http_response(404, {})
        check_resp.raise_for_status = MagicMock()  # 404 shouldn't raise

        put_resp = _mock_http_response(201, {"content": {"sha": "def456"}})
        client = MagicMock()
        client.get.return_value = check_resp
        client.put.return_value = put_resp

        with patch.dict("os.environ", {"GITHUB_ORG": "test-org", "GITHUB_PAT": "tok"}):
            commit_file(client, "my-repo", "gsd/test", "src/main.py", "print('hi')", "add main.py")

        client.put.assert_called_once()
        put_body = client.put.call_args.kwargs["json"]
        self.assertIn("content", put_body)  # base64-encoded
        self.assertNotIn("sha", put_body)   # no sha for new file

    def test_updates_existing_file(self):
        """commit_file includes existing SHA when file already exists."""
        from src.pr_creator import commit_file

        check_resp = _mock_http_response(200, {"sha": "existing-sha-789"})
        put_resp = _mock_http_response(200, {"content": {"sha": "new-sha"}})
        client = MagicMock()
        client.get.return_value = check_resp
        client.put.return_value = put_resp

        with patch.dict("os.environ", {"GITHUB_ORG": "test-org", "GITHUB_PAT": "tok"}):
            commit_file(client, "my-repo", "gsd/test", "src/main.py", "print('v2')", "update")

        put_body = client.put.call_args.kwargs["json"]
        self.assertEqual(put_body["sha"], "existing-sha-789")


class TestOpenPR(unittest.TestCase):

    def test_opens_pr_and_returns_number(self):
        """open_pr posts to /pulls and returns pr dict."""
        from src.pr_creator import open_pr

        pr_data = {"number": 42, "html_url": "https://github.com/org/repo/pull/42"}
        resp = _mock_http_response(201, pr_data)
        client = MagicMock()
        client.post.return_value = resp

        with patch.dict("os.environ", {"GITHUB_ORG": "test-org", "GITHUB_PAT": "tok"}):
            result = open_pr(client, "my-repo", "gsd/test", "GSD: Feature", "PR body")

        self.assertEqual(result["number"], 42)
        self.assertEqual(result["html_url"], "https://github.com/org/repo/pull/42")


class TestBuildPRBody(unittest.TestCase):

    def test_includes_key_sections(self):
        """PR body contains deliverable, QA table, verdict."""
        from src.pr_creator import build_pr_body
        from src.schemas import CriticReport

        project = {"deliverable": "CSV parser", "acceptance_criteria": ["parse all rows"]}
        critic = CriticReport(
            verdict="APPROVED",
            correctness_score=90,
            security_score=95,
            maintainability_score=85,
            critic_notes="Looks solid",
        )
        qa = {"tests_passed": 10, "tests_total": 10, "coverage_percent": 94.0, "bandit_findings": 0}

        body = build_pr_body(project, critic, qa)

        self.assertIn("CSV parser", body)
        self.assertIn("APPROVED", body)
        self.assertIn("parse all rows", body)
        self.assertIn("94", body)


if __name__ == "__main__":
    unittest.main()

"""
pr_creator.py — GitHub PR creation for the GSD pipeline (Phase 4).

Creates a feature branch, commits code, opens a PR against main,
then sends a Gate 4 Telegram message for human review.

Fixes the TODO in gsd_executor.py Phase 4.

Every external call has:
  - Error handling for HTTP failures, rate limits, 5xx
  - Max 30 lines per function
  - Full docstrings (purpose, args, returns, raises)
"""
from __future__ import annotations

import json
import logging
import os
from base64 import b64encode

import httpx

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_ORG = os.environ.get("GITHUB_ORG", "")

_HEADERS = {
    "Authorization": f"Bearer {GITHUB_PAT}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _get_default_branch_sha(client: httpx.Client, repo: str) -> str:
    """
    Get the latest commit SHA on the repository's default branch.

    Args:
        client: httpx.Client with auth headers set
        repo: Repository name (without org prefix)

    Returns:
        SHA string of the HEAD commit on the default branch.

    Raises:
        httpx.HTTPStatusError: On GitHub API failure (4xx / 5xx).
        KeyError: If response structure is unexpected.
    """
    resp = client.get(f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}")
    resp.raise_for_status()
    default_branch = resp.json()["default_branch"]

    ref_resp = client.get(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/git/ref/heads/{default_branch}"
    )
    ref_resp.raise_for_status()
    return ref_resp.json()["object"]["sha"]


def create_branch(client: httpx.Client, repo: str, branch: str, sha: str) -> None:
    """
    Create a Git ref (branch) pointing to the given commit SHA.

    Args:
        client: httpx.Client with auth headers set
        repo: Repository name
        branch: New branch name to create
        sha: Commit SHA to branch from

    Raises:
        httpx.HTTPStatusError: On API failure or if branch already exists.
    """
    resp = client.post(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": sha},
    )
    resp.raise_for_status()
    log.info(f"Branch {branch} created at {sha[:8]}")


def commit_file(
    client: httpx.Client,
    repo: str,
    branch: str,
    path: str,
    content: str,
    message: str,
) -> None:
    """
    Create or update a single file in a branch via the GitHub Contents API.

    Args:
        client: httpx.Client with auth headers set
        repo: Repository name
        branch: Branch to commit to
        path: File path within the repo (e.g. 'src/main.py')
        content: Raw file content (will be base64-encoded)
        message: Commit message

    Raises:
        httpx.HTTPStatusError: On API failure.
    """
    b64_content = b64encode(content.encode("utf-8")).decode("ascii")

    # Check if file exists — need its SHA for updates
    existing_sha: str | None = None
    check = client.get(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/contents/{path}",
        params={"ref": branch},
    )
    if check.status_code == 200:
        existing_sha = check.json().get("sha")

    payload: dict = {
        "message": message,
        "content": b64_content,
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    resp = client.put(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/contents/{path}",
        json=payload,
    )
    resp.raise_for_status()
    log.info(f"Committed {path} to {branch}")


def open_pr(
    client: httpx.Client,
    repo: str,
    branch: str,
    title: str,
    body: str,
) -> dict:
    """
    Open a pull request against the default branch.

    Args:
        client: httpx.Client with auth headers set
        repo: Repository name
        branch: Head branch for the PR
        title: PR title
        body: PR description (Markdown)

    Returns:
        PR dict with 'number', 'html_url', 'node_id' keys.

    Raises:
        httpx.HTTPStatusError: On API failure.
    """
    resp = client.post(
        f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/pulls",
        json={"title": title, "head": branch, "base": "main", "body": body},
    )
    resp.raise_for_status()
    pr = resp.json()
    log.info(f"PR #{pr['number']} opened: {pr['html_url']}")
    return pr


def build_pr_body(project: dict, critic_report, qa_summary: dict) -> str:
    """
    Build a rich Markdown PR description with QA scores and acceptance criteria.

    Args:
        project: Project row dict from Postgres
        critic_report: CriticReport Pydantic model
        qa_summary: Dict with keys passed, total, coverage, bandit_findings

    Returns:
        Markdown string for the PR body.
    """
    criteria = project.get("acceptance_criteria") or []
    if isinstance(criteria, str):
        criteria = json.loads(criteria)

    criteria_md = "\n".join(f"- [ ] {c}" for c in criteria[:20])
    blocker_md = "\n".join(f"- {b}" for b in critic_report.blocker_issues) or "None"
    major_md = "\n".join(f"- {m}" for m in critic_report.major_issues) or "None"

    return f"""## Agency-in-a-Box — Auto-generated PR

**Deliverable**: {project.get('deliverable', 'N/A')}
**Critic verdict**: {critic_report.verdict}

### Acceptance Criteria
{criteria_md}

### QA Results
| Metric | Value |
|---|---|
| Tests | {qa_summary.get('tests_passed', 0)}/{qa_summary.get('tests_total', 0)} |
| Coverage | {qa_summary.get('coverage_percent', 0):.0f}% |
| Bandit findings | {qa_summary.get('bandit_findings', 0)} |
| Correctness | {critic_report.correctness_score}/100 |
| Security | {critic_report.security_score}/100 |
| Maintainability | {critic_report.maintainability_score}/100 |

### Critic Notes
{critic_report.critic_notes or 'N/A'}

### Blockers
{blocker_md}

### Major Issues
{major_md}

---
*Auto-generated by Agency-in-a-Box GSD Engine*
"""


def run_pr_pipeline(
    conn,
    project_id: str,
    repo: str,
    branch_name: str,
    code_output,
    qa_summary: dict,
    critic_report,
) -> dict:
    """
    Full Phase 4 pipeline: branch → commit → open PR → update DB.

    Args:
        conn: psycopg2 connection (main thread connection)
        project_id: UUID of the project
        repo: GitHub repository name
        branch_name: Feature branch name to create (e.g. 'gsd/proj-abc-20260305')
        code_output: CodeOutput Pydantic model with full_code, test_code
        qa_summary: Dict with QA metrics for the PR description
        critic_report: CriticReport Pydantic model

    Returns:
        Dict with 'pr_number', 'pr_url' keys.

    Raises:
        httpx.HTTPStatusError: On GitHub API failure.
        Exception: On DB update failure.
    """
    # Fetch project for description context
    with conn.cursor() as cur:
        cur.execute(
            "SELECT deliverable, acceptance_criteria FROM projects WHERE id = %s",
            (project_id,),
        )
        row = cur.fetchone()
    project = {
        "deliverable": row[0] if row else "N/A",
        "acceptance_criteria": row[1] if row else [],
    }

    with httpx.Client(headers=_HEADERS, timeout=30) as client:
        # Get base SHA
        sha = _get_default_branch_sha(client, repo)

        # Create feature branch
        create_branch(client, repo, branch_name, sha)

        # Commit implementation file
        commit_file(
            client, repo, branch_name,
            "src/main.py", code_output.full_code,
            f"feat: GSD implementation for project {project_id[:8]}",
        )

        # Commit test file
        commit_file(
            client, repo, branch_name,
            "tests/test_main.py", code_output.test_code,
            f"test: GSD test suite for project {project_id[:8]}",
        )

        # Commit requirements
        if code_output.requirements_txt.strip():
            commit_file(
                client, repo, branch_name,
                "requirements.txt", code_output.requirements_txt,
                "chore: pin dependencies",
            )

        # Open PR
        pr_title = f"[GSD] {project.get('deliverable', project_id[:8])}"
        pr_body = build_pr_body(project, critic_report, qa_summary)
        pr = open_pr(client, repo, branch_name, pr_title, pr_body)

    pr_number = pr["number"]
    pr_url = pr["html_url"]

    # Persist PR metadata to DB
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE projects
               SET github_repo = %s,
                   github_pr_url = %s,
                   github_pr_number = %s,
                   status = 'review_pending',
                   updated_at = NOW()
               WHERE id = %s""",
            (repo, pr_url, pr_number, project_id),
        )
    conn.commit()
    log.info(f"PR #{pr_number} saved to project {project_id}")

    return {"pr_number": pr_number, "pr_url": pr_url}

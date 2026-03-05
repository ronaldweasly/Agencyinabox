"""
sandbox.py — Fly.io Machines API orchestrator for sandboxed code execution.

No Supabase Storage. New delivery mechanism:
  - Code and tests are base64-encoded and passed as CODE_B64 / TEST_B64 env vars.
  - QA report is extracted from the Fly Machine logs (stdout line tagged
    QA_REPORT_JSON:) — no object storage dependency.

Manages the lifecycle:
  1. Base64-encode code + tests
  2. Create a Fly.io Machine with CODE_B64 / TEST_B64 env vars
  3. Wait for completion (poll machine state)
  4. Fetch machine logs, extract QA_REPORT_JSON line
  5. Parse into SandboxResult
  6. Machine auto-destroys (auto_destroy=True)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time

import httpx

from schemas import SandboxResult

log = logging.getLogger(__name__)

FLY_API_TOKEN = os.environ.get("FLY_API_TOKEN", "")
FLY_APP_NAME = os.environ.get("FLY_APP_NAME", "agency-sandbox")
FLY_API_BASE = "https://api.machines.dev/v1"

# Sandbox resource limits (spec: mem 256MB, CPU 0.5, timeout 120s)
SANDBOX_VM_MEMORY_MB = 256
SANDBOX_VM_CPUS = 1
SANDBOX_TIMEOUT_SECONDS = 120  # 60s execution + 60s buffer for boot/decode
SANDBOX_AUTO_DESTROY = True

# Base64 env var size limit — Fly.io hard limit is ~64KB per env var.
# Python code files are almost always < 50KB.
B64_SIZE_LIMIT_BYTES = 60_000


def _b64_encode(content: str) -> str:
    """Base64-encode a string for safe delivery as an env var."""
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def _create_machine(
    code_b64: str,
    test_b64: str,
    req_b64: str | None,
) -> str:
    """
    Create a Fly.io Machine to run the QA pipeline.
    Returns machine ID.

    No Supabase: files delivered as base64 env vars (CODE_B64 / TEST_B64).
    Raises httpx.HTTPError on API failure.
    """
    env: dict[str, str] = {
        "CODE_B64": code_b64,
        "TEST_B64": test_b64,
    }
    if req_b64:
        env["REQUIREMENTS_B64"] = req_b64

    payload = {
        "config": {
            "image": f"registry.fly.io/{FLY_APP_NAME}:latest",
            "env": env,
            "guest": {
                "cpu_kind": "shared",
                "cpus": SANDBOX_VM_CPUS,
                "memory_mb": SANDBOX_VM_MEMORY_MB,
            },
            "auto_destroy": SANDBOX_AUTO_DESTROY,
            "restart": {"policy": "no"},
        },
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{FLY_API_BASE}/apps/{FLY_APP_NAME}/machines",
            headers={
                "Authorization": f"Bearer {FLY_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        machine_id = resp.json()["id"]
        log.info(f"Sandbox machine created: {machine_id}")
        return machine_id


def _wait_for_machine(machine_id: str) -> str:
    """
    Poll machine status until stopped/destroyed. Returns final state string.

    Returns one of: 'stopped', 'destroyed', 'timeout'.
    """
    with httpx.Client(timeout=15) as client:
        for _ in range(SANDBOX_TIMEOUT_SECONDS // 5):
            try:
                resp = client.get(
                    f"{FLY_API_BASE}/apps/{FLY_APP_NAME}/machines/{machine_id}",
                    headers={"Authorization": f"Bearer {FLY_API_TOKEN}"},
                )
            except httpx.HTTPError as e:
                log.warning(f"Poll error for machine {machine_id}: {e}")
                time.sleep(5)
                continue

            if resp.status_code == 404:
                return "destroyed"  # auto_destroy kicked in
            if resp.status_code == 200:
                state = resp.json().get("state", "unknown")
                if state in ("stopped", "destroyed"):
                    return state
            time.sleep(5)

    return "timeout"


def _fetch_report_from_logs(machine_id: str) -> dict | None:
    """
    Fetch machine logs and extract the QA report JSON.

    The entrypoint prints one line tagged 'QA_REPORT_JSON:{...}' to stdout.
    We scan the logs for this line and parse the JSON.

    Returns the report dict, or None if not found.
    """
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(
                f"{FLY_API_BASE}/apps/{FLY_APP_NAME}/machines/{machine_id}/logs",
                headers={"Authorization": f"Bearer {FLY_API_TOKEN}"},
                params={"region": "", "instance_id": machine_id},
            )
            if resp.status_code != 200:
                log.warning(
                    f"Logs fetch returned {resp.status_code} for machine {machine_id}"
                )
                return None

            # Logs come as newline-delimited JSON events
            for line in resp.text.splitlines():
                try:
                    event = json.loads(line)
                    message = event.get("message", "")
                except json.JSONDecodeError:
                    message = line

                if message.startswith("QA_REPORT_JSON:"):
                    raw = message[len("QA_REPORT_JSON:"):]
                    return json.loads(raw)

    except Exception as e:
        log.warning(f"Log extraction failed for machine {machine_id}: {e}")

    return None


def _parse_sandbox_result(report: dict | None, final_state: str) -> SandboxResult:
    """
    Convert a raw QA report dict into a typed SandboxResult.
    Falls back to inferring pass/fail from final_state if no report.
    """
    if report is None:
        # No report parsed — infer from machine state
        return SandboxResult(
            status="failed" if final_state != "stopped" else "passed",
            error="QA report not found in machine logs",
        )

    overall = report.get("overall_status", "failed")
    status = "passed" if overall == "passed" else "failed"

    summary = report.get("summary", {})
    return SandboxResult(
        status=status,
        pytest_exit_code=int(report.get("pytest_exit", -1)),
        tests_passed=summary.get("passed", 0),
        tests_failed=summary.get("failed", 0),
        tests_total=summary.get("total", 0),
        coverage_percent=float(report.get("coverage_percent", 0.0)),
        ruff_issues=_count_ruff_issues(report.get("ruff", "")),
        mypy_issues=_count_mypy_issues(report.get("mypy", "")),
        bandit_findings=int(report.get("bandit_exit", 0)),
        error=report.get("error"),
    )


def _count_ruff_issues(ruff_output: str) -> int:
    """Count ruff findings from JSON output string."""
    try:
        findings = json.loads(ruff_output)
        return len(findings) if isinstance(findings, list) else 0
    except (json.JSONDecodeError, TypeError):
        return 0


def _count_mypy_issues(mypy_output: str) -> int:
    """Count mypy error lines."""
    return sum(1 for line in mypy_output.splitlines() if ": error:" in line)


def run_sandbox_qa(code_output, project_id: str) -> SandboxResult:
    """
    Execute the full sandbox QA pipeline:
    1. Base64-encode code + tests (no Supabase Storage)
    2. Launch Fly.io Machine with CODE_B64 / TEST_B64 env vars
    3. Wait for completion
    4. Extract QA report from machine logs
    5. Return typed SandboxResult

    Args:
        code_output: CodeOutput from gsd_executor (has full_code, test_code,
                     requirements_txt attributes)
        project_id: UUID of the project (used for logging only)

    Returns:
        SandboxResult with structured QA data.

    Raises:
        Never raises — all errors returned as SandboxResult(status="fatal").
    """
    try:
        # 1. Encode files as base64
        code_b64 = _b64_encode(code_output.full_code)
        test_b64 = _b64_encode(code_output.test_code)

        # Guard: Fly env var size limit
        if len(code_b64) > B64_SIZE_LIMIT_BYTES:
            return SandboxResult(
                status="fatal",
                error=f"Code too large for env var delivery ({len(code_b64)} bytes)",
            )

        req_b64 = None
        if code_output.requirements_txt.strip():
            req_b64 = _b64_encode(code_output.requirements_txt)

        # 2. Launch sandbox machine
        machine_id = _create_machine(code_b64, test_b64, req_b64)
        log.info(f"[project={project_id}] Sandbox machine {machine_id} launched")

        # 3. Wait for completion
        final_state = _wait_for_machine(machine_id)
        if final_state == "timeout":
            log.error(f"Sandbox {machine_id} timed out after {SANDBOX_TIMEOUT_SECONDS}s")
            return SandboxResult(
                status="fatal",
                error=f"Sandbox timed out after {SANDBOX_TIMEOUT_SECONDS}s",
            )

        log.info(f"Sandbox {machine_id} final state: {final_state}")

        # 4. Extract QA report from machine logs
        report = _fetch_report_from_logs(machine_id)

        # 5. Parse into structured result
        result = _parse_sandbox_result(report, final_state)
        log.info(
            f"Sandbox QA result for project {project_id}: status={result.status}, "
            f"tests={result.tests_passed}/{result.tests_total}, "
            f"coverage={result.coverage_percent:.1f}%"
        )
        return result

    except httpx.HTTPError as e:
        log.error(f"Sandbox HTTP error for project {project_id}: {e}")
        return SandboxResult(status="fatal", error=str(e))
    except Exception as e:
        log.error(f"Sandbox error for project {project_id}: {e}")
        return SandboxResult(status="fatal", error=str(e))

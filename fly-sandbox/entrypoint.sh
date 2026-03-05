#!/bin/bash
# ============================================================================
# entrypoint.sh — Fly.io sandbox QA pipeline
#
# Fixes applied from PROBLEMS.md:
#   P-11: Shell injection ELIMINATED — tool outputs written to temp files,
#         then read by Python via file read. No shell expansion of untrusted
#         content inside Python strings.
#   P-12: Comment clarified — set -euo pipefail protects the decode phase.
#         QA tools use explicit exit code capture (intentional, not a bug).
#   P-13: (Superseded) Files are now delivered as CODE_B64/TEST_B64
#         base64-encoded environment variables — no wget, no URLs needed.
#         This removes the Supabase Storage dependency entirely.
#   Bug #6: Exit code is $PYTEST_EXIT (not always 0).
#   Bug #7: Report file existence validated before parsing.
#   Bug #8: Test file delivered via separate env var (TEST_B64).
#   Export fix: BANDIT_EXIT and PYTEST_EXIT exported BEFORE the Python
#               heredoc so os.environ can read them inside the script.
# ============================================================================

# set -euo pipefail protects the decode phase. QA tool errors are captured
# explicitly below (each tool's exit code is stored in a variable).
set -euo pipefail

# ── Validate required env vars ─────────────────────────────────────────────
: "${CODE_B64:?CODE_B64 environment variable is required}"
: "${TEST_B64:?TEST_B64 environment variable is required}"

REPORT_PATH="/workspace/qa_report.json"
echo '{"status":"starting"}' > "$REPORT_PATH"

# ── Decode phase (set -e protects these) ──────────────────────────────────
echo "Decoding code payload..."
echo "$CODE_B64" | base64 -d > /workspace/main.py
if [ ! -s /workspace/main.py ]; then
    echo '{"status":"fatal","error":"Code payload decode failed or empty"}' > "$REPORT_PATH"
    exit 1
fi

echo "Decoding test payload..."
echo "$TEST_B64" | base64 -d > /workspace/test_main.py
if [ ! -s /workspace/test_main.py ]; then
    echo '{"status":"fatal","error":"Test payload decode failed or empty"}' > "$REPORT_PATH"
    exit 1
fi

# Optional requirements.txt delivered as base64
if [ -n "${REQUIREMENTS_B64:-}" ]; then
    echo "Decoding requirements.txt..."
    echo "$REQUIREMENTS_B64" | base64 -d > /workspace/requirements.txt
    pip install --no-cache-dir -r /workspace/requirements.txt \
        2>/workspace/pip_stderr.txt || true
fi

# ── QA collection phase (errors captured, not fatal) ──────────────────────

# P-11 fix: Write all tool outputs to files instead of shell variables.
# This prevents shell injection via crafted code output containing
# triple quotes, backslashes, or other shell/Python metacharacters.

echo "Running ruff static analysis..."
ruff check /workspace/main.py --output-format=json \
    > /workspace/ruff_output.json 2>&1 || true

echo "Running mypy type check..."
mypy /workspace/main.py --ignore-missing-imports \
    > /workspace/mypy_output.txt 2>&1 || true

echo "Running bandit security scan..."
BANDIT_EXIT=0
bandit -r /workspace/main.py -f json \
    > /workspace/bandit_output.json 2>&1 || BANDIT_EXIT=$?

echo "Running pytest with coverage..."
PYTEST_EXIT=0
pytest /workspace/test_main.py \
    --json-report --json-report-file="$REPORT_PATH" \
    --cov=/workspace --cov-report=json:/workspace/coverage.json \
    --cov-fail-under=90 \
    --tb=short \
    2>/workspace/pytest_stderr.txt || PYTEST_EXIT=$?

# Bug #7 fix: Validate report was actually generated
if [ ! -f "$REPORT_PATH" ] || [ ! -s "$REPORT_PATH" ]; then
    echo '{"status":"fatal","error":"QA report not generated - possible import error"}' \
        > "$REPORT_PATH"
    exit 1
fi

# Export fix: export BEFORE the Python heredoc so os.environ can read them
export BANDIT_EXIT
export PYTEST_EXIT

# ── P-11 fix: Assemble final report safely in Python ──────────────────────
# All tool outputs are READ FROM FILES — no shell variable expansion inside
# Python strings. This eliminates the sandbox escape vector entirely.
# The final report is printed to stdout tagged with QA_REPORT_JSON: so that
# sandbox.py can extract it from the Fly Machine logs API without any
# object storage dependency.

python3 << 'PYTHON_EOF'
import json
import os

REPORT_PATH = "/workspace/qa_report.json"

def safe_read(path, max_bytes=4000):
    """Read a file safely, truncating to max_bytes."""
    try:
        with open(path, "r") as f:
            return f.read(max_bytes)
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"Error reading {path}: {e}"

def safe_read_json(path):
    """Read a JSON file safely, return dict or empty dict."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Load pytest report (written by pytest-json-report)
try:
    with open(REPORT_PATH, "r") as f:
        report = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    report = {"status": "fatal", "error": "Failed to parse pytest report"}

# Inject QA tool results from FILES (not shell variables — P-11 fix)
report["ruff"] = safe_read("/workspace/ruff_output.json")
report["mypy"] = safe_read("/workspace/mypy_output.txt")
report["bandit"] = safe_read("/workspace/bandit_output.json")

# Export fix: now available because exported before this heredoc
report["bandit_exit"] = int(os.environ.get("BANDIT_EXIT", "-1"))
report["pytest_exit"] = int(os.environ.get("PYTEST_EXIT", "-1"))

# Read coverage data
coverage = safe_read_json("/workspace/coverage.json")
if "totals" in coverage:
    report["coverage_percent"] = coverage["totals"].get("percent_covered", 0)

# Determine overall status
if report.get("pytest_exit", -1) == 0 and report.get("bandit_exit", -1) == 0:
    report["overall_status"] = "passed"
else:
    report["overall_status"] = "failed"

with open(REPORT_PATH, "w") as f:
    json.dump(report, f, indent=2)

# Print report to stdout tagged for sandbox.py log extraction
# (no Supabase Storage — report travels via Fly Machine logs)
print("QA_REPORT_JSON:" + json.dumps(report))
print(f"QA pipeline complete: overall_status={report['overall_status']}")
PYTHON_EOF

# Bug #6 fix: Exit with pytest's actual exit code
exit $PYTEST_EXIT

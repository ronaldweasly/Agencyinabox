# Agency-in-a-Box Blueprint — Full Problem Audit

**Date**: 2026-03-05
**Source**: `Agency-in-a-Box-Complete-Blueprint.docx`
**Issues Found**: 27 (7 Critical, 9 High, 7 Medium, 4 Low)

---

## CATEGORY 1: SPEC CONTRADICTIONS (The doc disagrees with itself)

### P-01 [CRITICAL] — Redis mentioned despite "No Redis" spec
- **Location**: Section 1.1, Data Journey diagram
- **Problem**: `"Redis mutex locks lead — no follow-up fires while waiting"` appears in the
  outreach flow, but the spec explicitly says **"No Kafka, no Redis, no Temporal"** and
  mandates **"Postgres row-lock mutex"** for reply locking.
- **Impact**: If someone follows the diagram, they'll add Redis. If they follow the spec,
  the diagram is wrong.
- **Fix**: Replace with Postgres `SELECT ... FOR UPDATE` row lock on the lead row.

### P-02 [MEDIUM] — "14 bugs fixed" but spec only lists 12
- **Location**: Step 4 header says "all 14 bugs fixed", but the known-bugs list in the
  master prompt and schema comments reference only 12 numbered bugs. The SQL comments
  reference "Fix 13" and "Fix 14" which don't exist in the enumerated list.
- **Fix**: The SQL comments `-- Fix 5 & 6`, `-- Fix 10, 12, 13`, `-- Fix 14` use
  different numbering than the master bug list. Renumber consistently.

### P-03 [MEDIUM] — n8n mentioned but not in tech stack
- **Location**: Section 2 (Technology Stack table) mentions n8n as a "traffic cop" for
  webhooks. But the master spec has no mention of n8n, and the actual webhook handling
  is implemented entirely in the DMZ FastAPI (Step 6).
- **Impact**: Confusing for the builder — do they need n8n or not?
- **Fix**: Remove n8n. The DMZ FastAPI already handles all webhook routing.

### P-04 [LOW] — Max 200 lines vs max 30 lines per function
- **Location**: Phase 2 diagram says "Max 200 lines per module", but the master spec
  and the IMPLEMENTATION_SYSTEM prompt say "max 30 lines per function".
- **Impact**: These are not contradictory (module vs function), but the 200-line module
  limit is never enforced anywhere in code. Either enforce it or remove the claim.

---

## CATEGORY 2: CONNECTION SHARING / CONCURRENCY BUGS

### P-05 [CRITICAL] — Single connection shared between main loop and heartbeat thread
- **Location**: `worker_core.py` — `run_worker()` passes `conn` to both `claim_job()`
  and `heartbeat()`.
- **Problem**: `psycopg2` connections are **NOT thread-safe**. The heartbeat thread does
  `conn.commit()` every 30s on the SAME connection object that the main thread uses for
  `reserve_budget()`, `log_audit()`, and `execute_job()`. This causes:
  1. **Data corruption**: heartbeat commit can commit a half-finished budget transaction.
  2. **InterfaceError**: concurrent cursor operations on same connection.
  3. **Lost updates**: heartbeat rollback (on exception) rolls back main thread work.
- **Impact**: This is not a theoretical risk — it WILL crash in production under load.
- **Fix**: Heartbeat thread must use its **own dedicated connection**.

### P-06 [HIGH] — No connection health check or reconnection logic
- **Location**: `worker_core.py` — `get_connection()` is called once, connection used forever.
- **Problem**: Supabase/PgBouncer will drop idle connections. Network blips happen.
  The worker will crash with `OperationalError: server closed the connection unexpectedly`
  and never recover.
- **Fix**: Add connection health check (`SELECT 1`) with reconnection logic, or use a
  connection pool (e.g., `psycopg2.pool.ThreadedConnectionPool`).

### P-07 [HIGH] — Heartbeat exception handling is insufficient
- **Location**: `heartbeat()` function catches `Exception` but only logs a warning.
- **Problem**: If the heartbeat connection drops (P-06), the heartbeat silently stops
  working but the `stop_event` is never set. The job continues running but the watchdog
  will reclaim it because `updated_at` stops advancing. Now you have TWO workers
  processing the same job.
- **Fix**: On persistent heartbeat failure (e.g., 3 consecutive failures), set a shared
  flag that the main thread checks, causing it to abort the current job.

---

## CATEGORY 3: BUDGET / TRANSACTION BUGS

### P-08 [CRITICAL] — Budget reconciliation uses estimate, not actual cost
- **Location**: `run_worker()` — on failure, `release_budget(conn, estimated_cost, ...)`.
  On success, there's NO reconciliation of `estimated_cost` vs `actual_cost`.
- **Problem**: If `execute_job()` returns `actual_cost = 0.12` but `estimated_cost = 0.05`,
  you've consumed $0.12 of API credit but only reserved $0.05 in the budget. Over hundreds
  of jobs, your budget tracking becomes meaningless and you'll overspend.
- **Fix**: After successful execution, compute `delta = actual_cost - estimated_cost` and
  apply a correction UPDATE. On failure, release the `estimated_cost` (current behavior is
  correct for failure path).

### P-09 [HIGH] — `reserve_budget` can leave partial state on crash between two UPDATEs
- **Location**: `reserve_budget()` — the global UPDATE and project UPDATE are in separate
  `cur.execute()` calls. If the process crashes AFTER the global UPDATE succeeds but
  BEFORE the project UPDATE, the global spend is incremented but the project spend is not.
- **Problem**: The `conn.rollback()` on project failure correctly handles the logical path.
  BUT if the Python process is killed (OOM, SIGKILL) between the two statements and
  autocommit is off (it is), then the implicit transaction is rolled back by Postgres. This
  is actually OK because `conn.commit()` is only at the end. **However**, the two UPDATEs
  should still be explicitly in a single transaction block for clarity and safety.
- **Fix**: Wrap both UPDATEs in an explicit `BEGIN ... COMMIT` or ensure they stay in the
  same implicit transaction (they do, but add a comment explaining this).

### P-10 [MEDIUM] — `daily_spend` row might not exist for today
- **Location**: `reserve_budget()` — `WHERE date = CURRENT_DATE`.
- **Problem**: The INSERT in the schema only creates today's row at schema creation time.
  On the next day, there's no row for `CURRENT_DATE`, so the UPDATE matches 0 rows and
  `fetchone()` returns None. The budget guard treats this as "budget exceeded" and ALL
  jobs are permanently blocked.
- **Fix**: Use `INSERT ... ON CONFLICT DO NOTHING` before the UPDATE, or use an
  `UPSERT` pattern to ensure today's row always exists.

---

## CATEGORY 4: ENTRYPOINT / SANDBOX BUGS

### P-11 [CRITICAL] — Shell injection via Python string interpolation in entrypoint.sh
- **Location**: `entrypoint.sh` — the Python block at the end:
  ```python
  report['ruff'] = '''$RUFF_OUTPUT'''[:2000]
  report['mypy'] = '''$MYPY_OUTPUT'''[:2000]
  report['bandit'] = '''$BANDIT_OUTPUT'''[:3000]
  ```
- **Problem**: `$RUFF_OUTPUT`, `$MYPY_OUTPUT`, and `$BANDIT_OUTPUT` are shell-expanded
  INSIDE Python triple-quoted strings. If the output contains `'''` (triple quotes),
  backslashes, or other Python-special characters, the Python script crashes or executes
  arbitrary code. Since this processes AI-generated code output, an attacker who
  controls the input code can craft output that breaks out of the string.
- **Impact**: **Sandbox escape vector**. Attacker code can inject arbitrary Python
  into the QA report-writing step.
- **Fix**: Pass the values as environment variables and read them with `os.environ` in
  the Python block, or write each output to a temporary file and read it in Python.

### P-12 [HIGH] — `set -e` is partially defeated by `|| true` and `|| EXIT=`
- **Location**: `entrypoint.sh` — ruff and mypy use `|| true`, bandit uses `|| BANDIT_EXIT=$?`.
- **Problem**: `set -e` means "exit on any error", but every command is followed by
  `|| true` or `|| VAR=$?` which suppresses the error. So `set -e` is effectively
  useless here — the script never actually fails early. This contradicts the doc comment
  `"Fix 3: Fail immediately on ANY error"`.
- **Fix**: This is actually intentional for the QA pipeline (you want to collect ALL
  results even if ruff finds issues). But the comment is misleading. Update the comment
  to explain that `set -e` protects the download phase while `|| true` is deliberate
  for the QA collection phase.

### P-13 [MEDIUM] — Entrypoint takes URLs as positional args, not env vars
- **Location**: `entrypoint.sh` — `CODE_URL=$1` and `TEST_URL=$2`.
- **Problem**: The Fly.io deploy example uses `--env CODE_URL=...` but the entrypoint
  reads `$1` (positional arg). These are different mechanisms. The deploy command will
  fail silently — `$1` will be empty.
- **Fix**: Consistently use either env vars (`${CODE_URL}`) or positional args, not both.

### P-14 [LOW] — Dockerfile pins `wget` to a Debian-specific version
- **Location**: `fly-sandbox/Dockerfile` — `wget=1.21.3-1+b2`.
- **Problem**: This version string is specific to Debian Bookworm. When the base image
  updates to a new Debian release, the build breaks.
- **Fix**: Either pin the base image (`python:3.12.3-slim-bookworm`) to match, or don't
  pin wget's version (it's a system tool, not a security-sensitive dependency).

---

## CATEGORY 5: DMZ / SECURITY BUGS

### P-15 [CRITICAL] — Telegram webhook verification is wrong
- **Location**: `dmz/main.py` — `verify_telegram_signature()`.
- **Problem**: This function implements WebApp data verification (`WebAppData` key), but
  that's for Telegram Mini Apps, NOT for webhook callbacks. For webhooks, Telegram uses
  a `secret_token` header (`X-Telegram-Bot-Api-Secret-Token`) which the code ALSO checks
  separately. So:
  1. `verify_telegram_signature()` is dead code — never called.
  2. The actual auth relies solely on a static secret header comparison, which is fine
     but the dead function is misleading and could be called incorrectly later.
- **Fix**: Remove `verify_telegram_signature()` entirely. The `X-Telegram-Bot-Api-Secret-Token`
  header check is the correct approach for webhooks.

### P-16 [HIGH] — DMZ creates a new psycopg2 connection per reject request, never closes it
- **Location**: `handle_reject_pr()` — `conn = psycopg2.connect(DB_URL)` ... `conn.close()`.
- **Problem**: On success, the connection is closed. On exception, it leaks. No
  `try/finally` or context manager. Under repeated failures, this exhausts the
  Supabase connection pool.
- **Fix**: Use `with psycopg2.connect(DB_URL) as conn:` or a connection pool.

### P-17 [HIGH] — REJECT callback SQL injection via JSONB concatenation
- **Location**: `handle_reject_pr()`:
  ```python
  "UPDATE jobs SET status = 'pending', payload = payload || '{\"revision_requested\": true}' WHERE id = %s"
  ```
- **Problem**: The JSONB literal is hardcoded in the SQL string, which is fine HERE.
  But if this pattern is extended to include user input (e.g., rejection reason from
  Telegram), it becomes an injection vector. More importantly, this overwrites any
  existing `revision_requested` key without merging.
- **Fix**: Use parameterized JSONB: `payload || %s::jsonb` with a proper Python dict
  serialized via `json.dumps()`.

### P-18 [MEDIUM] — `callback_id` is received but never used for Telegram answer
- **Location**: `dmz/main.py` — `callback_id = callback.get('id')` is extracted but
  never passed to `answerCallbackQuery`. Telegram will show a spinning loader on the
  button indefinitely.
- **Fix**: After processing, call `answerCallbackQuery(callback_id)` to dismiss the
  loading state.

### P-19 [HIGH] — No rate limiting on DMZ endpoint
- **Location**: `dmz/main.py` — the `/internal/telegram/callback` endpoint.
- **Problem**: Despite being "internal", if the endpoint is exposed (even accidentally),
  there's no rate limiting. An attacker who discovers the webhook secret can spam
  merge/reject calls.
- **Fix**: Add rate limiting middleware (e.g., `slowapi`), or at minimum, log + alert
  on high request rates.

---

## CATEGORY 6: GSD EXECUTOR / CRITIC BUGS

### P-20 [HIGH] — `generate_code()` sends system prompt as `system=` kwarg
- **Location**: `gsd_executor.py` — `claude.chat.completions.create(..., system=IMPLEMENTATION_SYSTEM)`.
- **Problem**: The `instructor` library wrapping Anthropic doesn't necessarily pass a
  `system=` kwarg through to the Anthropic API. Depending on the instructor version,
  this may be silently ignored, meaning Claude never receives the mandatory rules
  (TDD, 30-line limit, citation requirements, etc.).
- **Fix**: Include the system prompt as a `{'role': 'system', 'content': ...}` message
  at the start of the messages list, OR verify with the specific instructor version
  that `system=` is supported.

### P-21 [MEDIUM] — `fetch_live_docs()` uses Firecrawl v0 API
- **Location**: `gsd_executor.py` — `search_url = 'https://api.firecrawl.dev/v0/search'`.
- **Problem**: Firecrawl is now on v1. The v0 endpoint may be deprecated or removed.
  The spec itself says "Phase 0 mandatory: check breaking changes" — ironic that the
  code doesn't follow its own rule.
- **Fix**: Update to v1 API (`/v1/search`), or better yet, make the version configurable.

### P-22 [MEDIUM] — Critic agent's `from_gemini()` instructor usage may be incorrect
- **Location**: `critic_agent.py` — `gemini = from_gemini(genai.GenerativeModel(...))`.
- **Problem**: The `instructor` library's `from_gemini` wrapper has changed APIs across
  versions. The `gemini.chat.completions.create()` call style may not work with
  current instructor versions. Also, `system=CRITIC_SYSTEM` as a kwarg has the same
  issue as P-20.
- **Fix**: Verify against pinned instructor version. Use messages-based system prompt.

### P-23 [MEDIUM] — CriticReport defined twice (gsd_executor.py AND critic_agent.py)
- **Location**: Both files define `class CriticReport(BaseModel)` with different fields.
  `gsd_executor.py` has 8 fields, `critic_agent.py` has 9 (adds `critic_notes`).
- **Problem**: Import confusion. Which one is canonical? If gsd_executor imports from
  critic_agent, the schema mismatch causes validation errors.
- **Fix**: Define shared Pydantic models in a single `schemas.py` module.

---

## CATEGORY 7: SCHEMA / OPERATIONAL ISSUES

### P-24 [HIGH] — No FK from `jobs.project_id` to `projects.id`
- **Location**: Schema SQL — `jobs` table has `project_id UUID REFERENCES project_budgets(project_id)`.
- **Problem**: Jobs reference `project_budgets`, not `projects`. This means:
  1. You can't easily join jobs to projects.
  2. A project must have a budget row BEFORE any job can be created for it.
  3. The `projects` table has its own `budget_id UUID REFERENCES project_budgets(project_id)`.
  This is a circular dependency — you need project_budgets to create a job, but
  project_budgets has no FK to projects.
- **Fix**: `jobs.project_id` should reference `projects.id`. Budget checks should join
  through `projects.budget_id → project_budgets.project_id`.

### P-25 [LOW] — `execute_job()` is called but never defined
- **Location**: `worker_core.py` — `actual_cost = execute_job(conn, job)` in `run_worker()`.
- **Problem**: The function is never defined in the blueprint. The reader has no idea
  what the interface contract is.
- **Fix**: Define a stub/interface with clear docstring explaining what it must return.

### P-26 [LOW] — GDPR cron doesn't handle `converted` leads separately
- **Location**: Schema SQL Part 4 — `AND status NOT IN ('converted', 'active_project')`.
- **Problem**: The spec says "Converted leads have separate retention policy" but the
  SQL only excludes them from deletion. There's no separate cron or TTL for converted
  leads. They're retained forever.
- **Fix**: Add a separate deletion clause for converted leads with a longer TTL (e.g.,
  365 days), or document that converted leads are retained indefinitely by design.

### P-27 [CRITICAL] — Watchdog CTE casting is wrong for interval
- **Location**: Schema SQL Part 4:
  ```sql
  AND updated_at < NOW() - (processing_timeout_seconds || ' seconds')::INTERVAL
  ```
- **Problem**: `processing_timeout_seconds` is an `INT` column. The expression
  `processing_timeout_seconds || ' seconds'` concatenates an integer with a string,
  which in Postgres requires an explicit cast: `(processing_timeout_seconds::TEXT || ' seconds')::INTERVAL`.
  Without the `::TEXT` cast, this produces a type error.
- **Fix**: Use `make_interval(secs => processing_timeout_seconds)` which is cleaner
  and type-safe.

---

## SUMMARY TABLE

| ID    | Severity | Category        | One-liner                                           |
|-------|----------|-----------------|-----------------------------------------------------|
| P-01  | CRITICAL | Spec conflict   | Redis in diagram, spec says no Redis                |
| P-02  | MEDIUM   | Spec conflict   | "14 bugs" claimed, only 12 listed                   |
| P-03  | MEDIUM   | Spec conflict   | n8n mentioned but not in stack/code                 |
| P-04  | LOW      | Spec conflict   | 200-line module limit never enforced                |
| P-05  | CRITICAL | Concurrency     | Shared psycopg2 conn between threads               |
| P-06  | HIGH     | Reliability     | No connection health check / reconnect              |
| P-07  | HIGH     | Concurrency     | Heartbeat failure doesn't abort job                 |
| P-08  | CRITICAL | Budget          | actual_cost never reconciled after success           |
| P-09  | HIGH     | Budget          | Two-phase budget update crash risk                  |
| P-10  | MEDIUM   | Budget          | daily_spend row missing for new day                 |
| P-11  | CRITICAL | Security        | Shell injection in entrypoint.sh Python block       |
| P-12  | HIGH     | Sandbox         | set -e defeated by || true everywhere               |
| P-13  | MEDIUM   | Sandbox         | Positional args vs env vars mismatch                |
| P-14  | LOW      | Sandbox         | Debian-specific wget version pin                    |
| P-15  | CRITICAL | Security        | Wrong Telegram signature verification (dead code)   |
| P-16  | HIGH     | Reliability     | Connection leak in DMZ reject handler               |
| P-17  | HIGH     | Security        | Hardcoded JSONB pattern, no parameterization        |
| P-18  | MEDIUM   | UX              | Telegram callback never answered (spinner)          |
| P-19  | HIGH     | Security        | No rate limiting on DMZ endpoint                    |
| P-20  | HIGH     | Integration     | system= kwarg may be ignored by instructor          |
| P-21  | MEDIUM   | Maintenance     | Firecrawl v0 API deprecated                         |
| P-22  | MEDIUM   | Integration     | from_gemini instructor API may be wrong             |
| P-23  | MEDIUM   | Architecture    | CriticReport defined twice with different schemas   |
| P-24  | HIGH     | Schema          | jobs FK points to budgets, not projects             |
| P-25  | LOW      | Completeness    | execute_job() never defined                         |
| P-26  | LOW      | GDPR            | Converted lead retention policy not implemented     |
| P-27  | CRITICAL | Schema          | Watchdog interval cast bug — type error at runtime  |

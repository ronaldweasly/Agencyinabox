-- ============================================================================
-- 001_schema.sql — Core database schema for Agency-in-a-Box
-- ============================================================================
-- Run in Supabase SQL editor in order.
--
-- Fixes applied:
--   P-24: jobs.project_id now references projects(id), not project_budgets
--   P-27: Watchdog uses make_interval() instead of broken string concatenation
--   P-10: daily_spend upsert function ensures today's row always exists
--   P-26: Converted leads have explicit 365-day retention
--   P-02: All comments use consistent numbering from PROBLEMS.md
-- ============================================================================

-- ── Budget tracking ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_spend (
    date        DATE PRIMARY KEY DEFAULT CURRENT_DATE,
    global_spend NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    global_cap   NUMERIC(10, 2) NOT NULL DEFAULT 15.00
);

CREATE TABLE IF NOT EXISTS project_budgets (
    project_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    current_spend NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    project_cap   NUMERIC(10, 2) NOT NULL DEFAULT 50.00,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Leads ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS leads (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_hash       TEXT UNIQUE NOT NULL,   -- peppered SHA-256 for dedup
    company_name      TEXT,
    website           TEXT,
    contact_email     TEXT,
    contact_name      TEXT,
    icp_score         INT,
    icp_reasoning     TEXT,
    status            VARCHAR(50) NOT NULL DEFAULT 'new',
    kvk_validated     BOOLEAN NOT NULL DEFAULT FALSE,
    last_contact_date TIMESTAMPTZ,            -- nullable; COALESCE with created_at for GDPR
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- P-01 fix: reply_mutex replaces Redis. Workers use SELECT ... FOR UPDATE on this row.
    reply_locked_by   VARCHAR(255),
    reply_locked_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain_hash);

-- ── Projects ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             UUID REFERENCES leads(id),
    budget_id           UUID REFERENCES project_budgets(project_id),
    deliverable         TEXT,
    tech_stack          JSONB,
    acceptance_criteria JSONB,
    gsd_task_tree       JSONB,
    status              VARCHAR(50) NOT NULL DEFAULT 'planning',
    github_repo         TEXT,
    github_pr_url       TEXT,
    github_pr_number    INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Job queue ───────────────────────────────────────────────────────────────
-- P-24 fix: project_id references projects(id), budget resolved via join.

CREATE TABLE IF NOT EXISTS jobs (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                 UUID REFERENCES projects(id),
    job_type                   VARCHAR(50) NOT NULL DEFAULT 'gsd_task',
    status                     VARCHAR(50) NOT NULL DEFAULT 'pending',
    worker_id                  VARCHAR(255),
    payload                    JSONB NOT NULL DEFAULT '{}',
    retry_count                INT NOT NULL DEFAULT 0,
    max_retries                INT NOT NULL DEFAULT 3,
    processing_timeout_seconds INT NOT NULL DEFAULT 300,
    review_deadline            TIMESTAMPTZ,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at);
-- Composite index for SKIP LOCKED claim query:
CREATE INDEX IF NOT EXISTS idx_jobs_pending_created
    ON jobs(created_at ASC) WHERE status = 'pending';

-- ── Audit log ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jobs_audit (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id        UUID REFERENCES jobs(id),
    old_status    VARCHAR(50),
    new_status    VARCHAR(50),
    worker_id     VARCHAR(255),
    error_message TEXT,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_job_id  ON jobs_audit(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_changed ON jobs_audit(changed_at);

-- ── Alerts / DLQ ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alerts (
    id          SERIAL PRIMARY KEY,
    alert_type  VARCHAR(50) NOT NULL,
    message     TEXT NOT NULL,
    job_id      UUID REFERENCES jobs(id),
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Idempotency keys ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key        TEXT PRIMARY KEY,
    result     JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-cleanup old idempotency keys (> 7 days)
-- Run as pg_cron: SELECT cleanup_idempotency_keys();
CREATE OR REPLACE FUNCTION cleanup_idempotency_keys() RETURNS void AS $$
    DELETE FROM idempotency_keys WHERE created_at < NOW() - INTERVAL '7 days';
$$ LANGUAGE sql;

-- ── GDPR cron monitoring ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cron_runs (
    id            SERIAL PRIMARY KEY,
    job_name      TEXT NOT NULL,
    rows_affected INT NOT NULL DEFAULT 0,
    success       BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    ran_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cron_runs_name ON cron_runs(job_name, ran_at DESC);

-- ── Helper: ensure today's daily_spend row exists ───────────────────────────
-- P-10 fix: called by reserve_budget before UPDATE.

CREATE OR REPLACE FUNCTION ensure_daily_spend() RETURNS void AS $$
    INSERT INTO daily_spend (date, global_spend, global_cap)
    VALUES (CURRENT_DATE, 0.00, 15.00)
    ON CONFLICT (date) DO NOTHING;
$$ LANGUAGE sql;

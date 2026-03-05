-- ============================================================================
-- 004_pg_cron.sql — Register scheduled jobs with pg_cron
-- ============================================================================
-- ⚠️  DO NOT run this against postgres:16-alpine (local Docker).
--     pg_cron is NOT available in Alpine. This script is for Supabase / managed
--     Postgres providers that bundle pg_cron.
--
-- For local dev, the watchdog + GDPR purge run as application-level cron or
-- are triggered manually.
-- ============================================================================
-- Run this ONCE in the Supabase / Postgres SQL editor after deploying the schema.
--
-- Requires: CREATE EXTENSION IF NOT EXISTS pg_cron;
--           (pg_cron is pre-installed on Supabase; for other providers see
--            https://github.com/citusdata/pg_cron)
--
-- Jobs registered:
--   1. Watchdog   — every 2 minutes  — reclaim stuck jobs
--   2. GDPR purge — daily at 02:00 UTC — delete expired leads
--   3. Budget reset — daily at 00:01 UTC — (handled by ensure_daily_spend())
--   4. Idempotency cleanup — weekly — delete old idempotency keys
-- ============================================================================

-- Guard: bail out immediately if pg_cron is not available
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron'
  ) THEN
    RAISE NOTICE '⚠️  pg_cron not available — skipping 004_pg_cron.sql (expected on Alpine/local dev)';
    RETURN;
  END IF;
END
$$;

-- Enable extension (harmless if already enabled)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ── 1. Watchdog — reclaim stuck jobs every 2 minutes ────────────────────────
-- Runs the CTE from 002_watchdog.sql inline.
SELECT cron.schedule(
    'watchdog',
    '*/2 * * * *',
    $$
    WITH reclaimed AS (
        UPDATE jobs
        SET status    = 'pending',
            worker_id = NULL,
            updated_at = NOW()
        WHERE status = 'processing'
          AND updated_at < NOW() - make_interval(secs => processing_timeout_seconds)
        RETURNING id, worker_id
    )
    INSERT INTO jobs_audit (job_id, old_status, new_status, worker_id, error_message)
    SELECT id, 'processing', 'pending', worker_id, 'timeout_recovery_by_watchdog'
    FROM reclaimed;
    $$
);

-- ── 2. GDPR purge — daily at 02:00 UTC ──────────────────────────────────────
-- Runs the DO block from 003_gdpr.sql.
SELECT cron.schedule(
    'gdpr_purge',
    '0 2 * * *',
    $$
    DO $$
    DECLARE
        deleted_unconverted INT;
        deleted_converted   INT;
    BEGIN
        DELETE FROM leads
        WHERE status NOT IN ('converted', 'active_project')
          AND COALESCE(last_contact_date, created_at) < NOW() - INTERVAL '30 days';
        GET DIAGNOSTICS deleted_unconverted = ROW_COUNT;

        DELETE FROM leads
        WHERE status = 'converted'
          AND COALESCE(last_contact_date, created_at) < NOW() - INTERVAL '365 days';
        GET DIAGNOSTICS deleted_converted = ROW_COUNT;

        INSERT INTO cron_runs (job_name, rows_affected, success)
        VALUES ('gdpr_purge', deleted_unconverted + deleted_converted, TRUE);
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO cron_runs (job_name, rows_affected, success, error_message)
        VALUES ('gdpr_purge', 0, FALSE, SQLERRM);
    END $$;
    $$
);

-- ── 3. Budget row seed — daily at 00:01 UTC ─────────────────────────────────
-- Ensures today's daily_spend row exists (P-10 fix: also called inline by
-- reserve_budget() but this guarantees it even before first job of the day).
SELECT cron.schedule(
    'budget_row_seed',
    '1 0 * * *',
    $$ SELECT ensure_daily_spend(); $$
);

-- ── 4. Idempotency key cleanup — weekly Sunday 03:00 UTC ────────────────────
SELECT cron.schedule(
    'idempotency_cleanup',
    '0 3 * * 0',
    $$ SELECT cleanup_idempotency_keys(); $$
);

-- ── Verify registered jobs ───────────────────────────────────────────────────
-- Run after this script to confirm:
-- SELECT jobid, jobname, schedule, command FROM cron.job ORDER BY jobname;

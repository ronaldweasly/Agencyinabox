-- ============================================================================
-- 003_gdpr.sql — GDPR TTL deletion cron (run daily at 02:00 UTC via pg_cron)
-- ============================================================================
-- P-26 fix: Converted leads have explicit 365-day retention (spec says
--           "separate retention policy" but original code just excluded them).
-- Bug #12 fix: COALESCE(last_contact_date, created_at) handles nullable column.
-- ============================================================================

DO $$
DECLARE
    deleted_unconverted INT;
    deleted_converted   INT;
BEGIN
    -- 1. Delete non-converted leads with no contact in 30 days
    DELETE FROM leads
    WHERE status NOT IN ('converted', 'active_project')
      AND COALESCE(last_contact_date, created_at) < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS deleted_unconverted = ROW_COUNT;

    -- 2. P-26 fix: Delete converted leads older than 365 days
    --    (separate retention policy as spec requires)
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

-- ── Health check (run every 25 hours, alert if GDPR cron missed) ────────────
-- If this returns 0, fire a Telegram alert.
-- SELECT COUNT(*) FROM cron_runs
-- WHERE job_name = 'gdpr_purge'
--   AND success = TRUE
--   AND ran_at > NOW() - INTERVAL '26 hours';

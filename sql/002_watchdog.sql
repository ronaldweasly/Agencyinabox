-- ============================================================================
-- 002_watchdog.sql — Reclaim stuck jobs (run every 2 minutes via pg_cron)
-- ============================================================================
-- P-27 fix: uses make_interval() instead of broken string concatenation.
-- Original: (processing_timeout_seconds || ' seconds')::INTERVAL
--   ↑ This fails because INT || TEXT requires explicit cast to TEXT first.
-- Fixed: make_interval(secs => processing_timeout_seconds) is type-safe.
-- ============================================================================

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

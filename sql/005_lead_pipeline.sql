-- ============================================================================
-- 005_lead_pipeline.sql — Additional tables for the lead-to-revenue pipeline
-- ============================================================================
-- Run AFTER 001_schema.sql. Adds:
--   - outreach_campaigns: tracks which leads are in which Instantly campaigns
--   - reply_threads: stores all inbound/outbound email messages per lead
--   - discovery_runs: audit log for lead discovery batches
--
-- These tables extend the core leads table from 001_schema.sql.
-- ============================================================================

-- ── Outreach campaigns ──────────────────────────────────────────────────────
-- Links leads to Instantly.ai campaigns.

CREATE TABLE IF NOT EXISTS outreach_campaigns (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    campaign_id TEXT NOT NULL,                     -- Instantly.ai campaign UUID
    status      VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, paused, completed, bounced
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event  VARCHAR(50),                       -- last Instantly event: sent, opened, replied, bounced
    last_event_at TIMESTAMPTZ,
    UNIQUE (lead_id, campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_outreach_lead     ON outreach_campaigns(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_campaign ON outreach_campaigns(campaign_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status   ON outreach_campaigns(status);

-- ── Reply threads ───────────────────────────────────────────────────────────
-- Stores all email messages (both directions) for conversation history.

CREATE TABLE IF NOT EXISTS reply_threads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    direction   VARCHAR(10) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    body        TEXT NOT NULL,
    status      VARCHAR(50) NOT NULL DEFAULT 'sent',
    -- inbound: always 'sent'
    -- outbound: 'pending_approval' → 'approved' → 'sent' / 'rejected'
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by VARCHAR(255),                      -- Telegram user who approved
    instantly_message_id TEXT,                      -- Instantly.ai message reference
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reply_lead    ON reply_threads(lead_id);
CREATE INDEX IF NOT EXISTS idx_reply_status  ON reply_threads(status);
CREATE INDEX IF NOT EXISTS idx_reply_sent    ON reply_threads(sent_at DESC);

-- ── Discovery runs ──────────────────────────────────────────────────────────
-- Audit trail for lead discovery batches.

CREATE TABLE IF NOT EXISTS discovery_runs (
    id              SERIAL PRIMARY KEY,
    queries         JSONB NOT NULL,                -- search queries used
    region          VARCHAR(10) NOT NULL DEFAULT 'NL',
    total_scraped   INT NOT NULL DEFAULT 0,
    unique_found    INT NOT NULL DEFAULT 0,
    inserted        INT NOT NULL DEFAULT 0,
    skipped_dupes   INT NOT NULL DEFAULT 0,
    enriched_count  INT NOT NULL DEFAULT 0,
    cost_estimate   NUMERIC(10, 4) NOT NULL DEFAULT 0.0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_discovery_started ON discovery_runs(started_at DESC);

-- ── Lead status transitions ─────────────────────────────────────────────────
-- Audit log for lead status changes (GDPR accountability).

CREATE TABLE IF NOT EXISTS lead_status_log (
    id          SERIAL PRIMARY KEY,
    lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    old_status  VARCHAR(50),
    new_status  VARCHAR(50) NOT NULL,
    changed_by  VARCHAR(255),                      -- worker_id or 'telegram:user_id'
    reason      TEXT,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_status_log ON lead_status_log(lead_id, changed_at DESC);

-- ── Add updated_at to leads if not present ──────────────────────────────────
-- (001_schema.sql may not have it)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE leads ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    END IF;
END $$;

-- ── Add category and city to leads if not present ───────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'category'
    ) THEN
        ALTER TABLE leads ADD COLUMN category TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'city'
    ) THEN
        ALTER TABLE leads ADD COLUMN city TEXT;
    END IF;
END $$;

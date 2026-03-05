-- ============================================================================
-- 007_growth_engine.sql — tables for the growth-engine features
-- ============================================================================

-- ── Competitor signals ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS competitor_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID REFERENCES leads(id),
    competitor_name TEXT NOT NULL,
    competitor_url  TEXT,
    signal_type     VARCHAR(50) NOT NULL,      -- 'ad_copy', 'pricing', 'feature_gap', 'review_weakness'
    detail          TEXT,
    found_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comp_signals_lead
    ON competitor_signals(lead_id, found_at DESC);

-- ── Campaign performance ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS campaign_performance (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID NOT NULL,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    emails_sent     INT NOT NULL DEFAULT 0,
    opens           INT NOT NULL DEFAULT 0,
    clicks          INT NOT NULL DEFAULT 0,
    replies         INT NOT NULL DEFAULT 0,
    positive_replies INT NOT NULL DEFAULT 0,
    unsubscribes    INT NOT NULL DEFAULT 0,
    bounces         INT NOT NULL DEFAULT 0,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (campaign_id, snapshot_date)
);

-- ── Extra columns on leads (idempotent) ─────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'recommended_service'
    ) THEN
        ALTER TABLE leads ADD COLUMN recommended_service TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'pain_point'
    ) THEN
        ALTER TABLE leads ADD COLUMN pain_point TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'pitch_angle'
    ) THEN
        ALTER TABLE leads ADD COLUMN pitch_angle TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'intent_signals'
    ) THEN
        ALTER TABLE leads ADD COLUMN intent_signals JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'competitor_intel'
    ) THEN
        ALTER TABLE leads ADD COLUMN competitor_intel JSONB DEFAULT '{}'::jsonb;
    END IF;
END $$;

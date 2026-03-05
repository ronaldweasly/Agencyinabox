-- ============================================================================
-- 006_companies.sql — Companies + AI Scores tables for the lead pipeline
-- ============================================================================
-- Required by: src/workers/ai_scoring_worker.py
-- Run after 001_schema.sql through 005_lead_pipeline.sql.
-- ============================================================================

-- ── Companies ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS companies (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    domain            TEXT UNIQUE,
    industry          TEXT,
    employee_count    INT,
    employee_range    VARCHAR(20),
    founded_year      INT,
    city              TEXT,
    state             VARCHAR(10),
    country           VARCHAR(10) DEFAULT 'US',
    tech_stack        JSONB DEFAULT '{}',
    pagespeed_score   INT,
    is_hiring         BOOLEAN NOT NULL DEFAULT FALSE,
    job_posting_count INT NOT NULL DEFAULT 0,
    is_advertising    BOOLEAN NOT NULL DEFAULT FALSE,
    funding_stage     TEXT,
    uses_wordpress    BOOLEAN NOT NULL DEFAULT FALSE,
    uses_shopify      BOOLEAN NOT NULL DEFAULT FALSE,
    ai_score          INT,
    qualified         BOOLEAN NOT NULL DEFAULT FALSE,
    qualification_tier VARCHAR(10),
    source            TEXT,
    source_query      TEXT,
    lead_id           UUID REFERENCES leads(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_qualified ON companies(qualified) WHERE qualified = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_tier ON companies(qualification_tier);
CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry);

-- ── AI Scores ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ai_scores (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id            UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    website_modernity     INT,
    tech_debt_signal      INT,
    automation_opp        INT,
    growth_signal         INT,
    company_maturity      INT,
    icp_fit               INT,
    digital_gap           INT,
    engagement_readiness  INT,
    composite_score       INT NOT NULL DEFAULT 0,
    score_tier            VARCHAR(10) NOT NULL DEFAULT 'cold',
    reasoning_summary     TEXT,
    key_signals           JSONB DEFAULT '[]',
    recommended_service   TEXT,
    email_hook            TEXT,
    model_version         TEXT,
    tokens_used           INT NOT NULL DEFAULT 0,
    scored_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_scores_company ON ai_scores(company_id);
CREATE INDEX IF NOT EXISTS idx_ai_scores_tier ON ai_scores(score_tier);
CREATE INDEX IF NOT EXISTS idx_ai_scores_composite ON ai_scores(composite_score DESC);

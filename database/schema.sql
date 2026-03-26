-- database/schema.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- ScrutinyAI — Supabase schema
-- Run this once in the Supabase SQL editor (or via psql) to create all tables.
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable UUID generation extension (already enabled on Supabase by default)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ── checks ────────────────────────────────────────────────────────────────────
-- One row per uploaded document.  The background worker updates this row
-- as the job progresses through the pipeline.

CREATE TABLE IF NOT EXISTS checks (
    id                   uuid         PRIMARY KEY,
    user_id              text         NOT NULL DEFAULT 'anonymous',
    filename             text         NOT NULL,

    -- Job lifecycle
    status               text         NOT NULL DEFAULT 'queued',
        CONSTRAINT checks_status_valid CHECK (
            status IN ('queued', 'processing', 'complete', 'failed')
        ),
    progress_percent     int          NOT NULL DEFAULT 0
        CONSTRAINT checks_progress_range CHECK (
            progress_percent BETWEEN 0 AND 100
        ),
    error_message        text,

    -- Result (populated when status = 'complete')
    result_json          text,                 -- full CheckResult serialised as JSON
    checked_at           timestamptz,
    total_ai_tokens_used int          NOT NULL DEFAULT 0,
    critical_count       int          NOT NULL DEFAULT 0,
    major_count          int          NOT NULL DEFAULT 0,
    minor_count          int          NOT NULL DEFAULT 0,

    -- Timestamps
    created_at           timestamptz  NOT NULL DEFAULT now(),
    updated_at           timestamptz  NOT NULL DEFAULT now()
);

-- Auto-update updated_at on every row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_checks_updated_at ON checks;
CREATE TRIGGER set_checks_updated_at
    BEFORE UPDATE ON checks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Index for fast status polling
CREATE INDEX IF NOT EXISTS idx_checks_status ON checks (status);
CREATE INDEX IF NOT EXISTS idx_checks_created_at ON checks (created_at DESC);


-- ── objection_feedback ────────────────────────────────────────────────────────
-- Stores advocate feedback on individual objections.
-- objection_id is the UUID from CheckResult.objections[*].id (stored in result_json).
-- job_id links back to checks.id.

CREATE TABLE IF NOT EXISTS objection_feedback (
    id             uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    objection_id   text         NOT NULL,
    job_id         text         NOT NULL,
    is_correct     boolean      NOT NULL,
    created_at     timestamptz  NOT NULL DEFAULT now()
);

-- Prevent duplicate feedback from the same session for the same objection
CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_unique_objection
    ON objection_feedback (objection_id, job_id);

-- Index for analytics queries
CREATE INDEX IF NOT EXISTS idx_feedback_job_id ON objection_feedback (job_id);


-- ── Row Level Security (RLS) ──────────────────────────────────────────────────
-- The backend uses the SERVICE_KEY which bypasses RLS.
-- Enable RLS anyway so anon/user keys cannot access raw data directly.

ALTER TABLE checks              ENABLE ROW LEVEL SECURITY;
ALTER TABLE objection_feedback  ENABLE ROW LEVEL SECURITY;

-- Service role has full access (Supabase grants this automatically for the
-- service key; these policies cover authenticated users if you add auth later)
CREATE POLICY "service_role_all_checks"
    ON checks FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_feedback"
    ON objection_feedback FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

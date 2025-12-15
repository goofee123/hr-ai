-- Migration: 012_merge_queue.sql
-- Description: Candidate merge/duplicate review queue
-- Sprint: R3 - Identity Resolution + Merge Queue

-- =============================================================================
-- CANDIDATE MERGE QUEUE TABLE
-- =============================================================================

-- Table for tracking duplicate candidates that need review
CREATE TABLE IF NOT EXISTS candidate_merge_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- The two candidates being compared
    primary_candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    duplicate_candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,

    -- Match details
    match_score DECIMAL(3,2) NOT NULL DEFAULT 0.50,  -- 0.00 to 1.00
    match_type VARCHAR(20) NOT NULL DEFAULT 'review',  -- hard, strong, fuzzy, review
    match_reasons JSONB DEFAULT '[]',  -- Array of {type, confidence, detail}

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, merged, rejected, deferred

    -- Review metadata
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- If merged, which candidate was kept
    merged_into_id UUID REFERENCES candidates(id),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure we don't have duplicate pairs (order independent)
    CONSTRAINT unique_candidate_pair UNIQUE (tenant_id, primary_candidate_id, duplicate_candidate_id),
    CONSTRAINT different_candidates CHECK (primary_candidate_id != duplicate_candidate_id)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_merge_queue_tenant_status
    ON candidate_merge_queue(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_merge_queue_match_type
    ON candidate_merge_queue(tenant_id, match_type);

CREATE INDEX IF NOT EXISTS idx_merge_queue_primary_candidate
    ON candidate_merge_queue(primary_candidate_id);

CREATE INDEX IF NOT EXISTS idx_merge_queue_duplicate_candidate
    ON candidate_merge_queue(duplicate_candidate_id);

CREATE INDEX IF NOT EXISTS idx_merge_queue_created_at
    ON candidate_merge_queue(created_at DESC);

-- Enable RLS
ALTER TABLE candidate_merge_queue ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY tenant_isolation_merge_queue
    ON candidate_merge_queue
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- =============================================================================
-- ADD SOFT DELETE COLUMN TO CANDIDATES (if not exists)
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'candidates' AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE candidates ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;
END
$$;

-- Index for soft deletes
CREATE INDEX IF NOT EXISTS idx_candidates_deleted_at
    ON candidates(deleted_at)
    WHERE deleted_at IS NOT NULL;

-- =============================================================================
-- UPDATE TRIGGER FOR updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_merge_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_merge_queue_updated_at ON candidate_merge_queue;
CREATE TRIGGER trigger_merge_queue_updated_at
    BEFORE UPDATE ON candidate_merge_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_merge_queue_updated_at();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE candidate_merge_queue IS 'Queue of potential duplicate candidates for human review';
COMMENT ON COLUMN candidate_merge_queue.match_type IS 'hard=auto-merge(95%+), strong=90%+, fuzzy=80-89%, review=60-79%';
COMMENT ON COLUMN candidate_merge_queue.match_reasons IS 'Array of {type: email_match|linkedin_match|name_similarity|company_overlap|phone_match, confidence: 0.0-1.0, detail: string}';

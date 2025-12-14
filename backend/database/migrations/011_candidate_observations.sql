-- =============================================================================
-- RECRUITING MODULE - CANONICAL CANDIDATE MODEL + OBSERVATIONS
-- Run this in Supabase Dashboard: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new
-- =============================================================================
-- Sprint R1: Transform candidate from resume-holder to rich entity with provenance
-- - Support multiple emails per candidate
-- - Store extracted facts as observations with confidence scores
-- - Track recruiter engagement via activity events
-- =============================================================================

-- =============================================================================
-- 1. CANDIDATE EMAILS (support multiple emails per candidate)
-- =============================================================================
CREATE TABLE IF NOT EXISTS candidate_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    source VARCHAR(100),  -- 'resume', 'linkedin', 'manual', 'form', 'import'
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure email uniqueness within tenant (same email = same person)
    CONSTRAINT uq_candidate_emails_tenant_email UNIQUE(tenant_id, email)
);

-- Indexes for candidate_emails
CREATE INDEX IF NOT EXISTS idx_candidate_emails_candidate ON candidate_emails(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_emails_email ON candidate_emails(email);
CREATE INDEX IF NOT EXISTS idx_candidate_emails_tenant ON candidate_emails(tenant_id);

-- Ensure only one primary email per candidate
CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_emails_primary
    ON candidate_emails(candidate_id)
    WHERE is_primary = TRUE;

-- =============================================================================
-- 2. CANDIDATE OBSERVATIONS (facts with provenance)
-- =============================================================================
-- Each observation is a fact extracted from a document with:
-- - source_document_id: which resume/document it came from
-- - confidence: 0.00-1.00 confidence score
-- - extraction_method: how it was extracted (llm, manual, linkedin, form)
-- - superseded_by_id: for tracking updates (newer observation supersedes older)
-- =============================================================================
CREATE TABLE IF NOT EXISTS candidate_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,

    -- Observation data
    field_name VARCHAR(100) NOT NULL,  -- 'current_title', 'years_experience', 'skill', 'education_degree', etc.
    field_value TEXT NOT NULL,
    value_type VARCHAR(50) DEFAULT 'string',  -- 'string', 'number', 'date', 'boolean', 'array'

    -- Provenance tracking
    source_document_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    extraction_method VARCHAR(50),  -- 'llm', 'manual', 'linkedin', 'form', 'import'
    confidence DECIMAL(3,2),  -- 0.00 to 1.00

    -- Supersession tracking (for updates)
    superseded_by_id UUID REFERENCES candidate_observations(id) ON DELETE SET NULL,
    is_current BOOLEAN DEFAULT TRUE,  -- FALSE if superseded

    -- Metadata
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    extracted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for candidate_observations
CREATE INDEX IF NOT EXISTS idx_candidate_observations_candidate ON candidate_observations(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_observations_field ON candidate_observations(candidate_id, field_name);
CREATE INDEX IF NOT EXISTS idx_candidate_observations_source ON candidate_observations(source_document_id);
CREATE INDEX IF NOT EXISTS idx_candidate_observations_current ON candidate_observations(candidate_id, is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_candidate_observations_tenant ON candidate_observations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_observations_field_value ON candidate_observations(field_name, field_value) WHERE is_current = TRUE;

-- =============================================================================
-- 3. CANDIDATE ACTIVITY EVENTS (recruiter engagement tracking)
-- =============================================================================
-- Event sourcing for all recruiter interactions with candidates
-- Used for engagement metrics, activity feeds, and analytics
-- =============================================================================
CREATE TABLE IF NOT EXISTS candidate_activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,

    -- Event data
    event_type VARCHAR(100) NOT NULL,  -- See event types below
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    application_id UUID REFERENCES applications(id) ON DELETE SET NULL,

    -- Event context (flexible JSONB for event-specific data)
    event_data JSONB DEFAULT '{}',

    -- Request context (for audit)
    ip_address INET,
    user_agent TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Event types reference:
-- 'profile_viewed'        - Recruiter opened candidate profile
-- 'resume_downloaded'     - Recruiter downloaded a resume
-- 'resume_uploaded'       - New resume uploaded for candidate
-- 'note_added'           - Recruiter added a comment/note
-- 'note_edited'          - Recruiter edited a comment/note
-- 'stage_changed'        - Candidate moved in pipeline
-- 'interview_scheduled'  - Interview booked
-- 'interview_completed'  - Interview finished
-- 'feedback_submitted'   - Scorecard/feedback submitted
-- 'offer_extended'       - Offer sent to candidate
-- 'offer_accepted'       - Candidate accepted offer
-- 'offer_declined'       - Candidate declined offer
-- 'rejected'             - Candidate rejected from pipeline
-- 'email_sent'           - Email sent to candidate
-- 'email_opened'         - Candidate opened email (if tracked)
-- 'tag_added'            - Tag added to candidate
-- 'tag_removed'          - Tag removed from candidate
-- 'merged'               - Candidate merged with another
-- 'source_changed'       - Application source updated

-- Indexes for candidate_activity_events
CREATE INDEX IF NOT EXISTS idx_candidate_activity_events_candidate ON candidate_activity_events(candidate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_activity_events_user ON candidate_activity_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_activity_events_type ON candidate_activity_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_activity_events_tenant ON candidate_activity_events(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_activity_events_application ON candidate_activity_events(application_id) WHERE application_id IS NOT NULL;

-- =============================================================================
-- 4. ENABLE ROW LEVEL SECURITY
-- =============================================================================
ALTER TABLE candidate_emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_activity_events ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 5. RLS POLICIES (tenant isolation)
-- =============================================================================
-- Note: These policies use app.tenant_id setting which may need adjustment
-- based on your authentication setup. For Supabase with service_role key,
-- RLS is bypassed. These are for added security with anon/authenticated roles.

-- candidate_emails policies
DO $$
BEGIN
    DROP POLICY IF EXISTS candidate_emails_tenant_isolation ON candidate_emails;
    CREATE POLICY candidate_emails_tenant_isolation ON candidate_emails
        FOR ALL USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'RLS policy creation skipped: %', SQLERRM;
END
$$;

-- candidate_observations policies
DO $$
BEGIN
    DROP POLICY IF EXISTS candidate_observations_tenant_isolation ON candidate_observations;
    CREATE POLICY candidate_observations_tenant_isolation ON candidate_observations
        FOR ALL USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'RLS policy creation skipped: %', SQLERRM;
END
$$;

-- candidate_activity_events policies
DO $$
BEGIN
    DROP POLICY IF EXISTS candidate_activity_events_tenant_isolation ON candidate_activity_events;
    CREATE POLICY candidate_activity_events_tenant_isolation ON candidate_activity_events
        FOR ALL USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'RLS policy creation skipped: %', SQLERRM;
END
$$;

-- =============================================================================
-- 6. HELPER FUNCTION: Get current observations for a candidate
-- =============================================================================
CREATE OR REPLACE FUNCTION get_candidate_current_observations(p_candidate_id UUID)
RETURNS TABLE (
    field_name VARCHAR(100),
    field_value TEXT,
    value_type VARCHAR(50),
    confidence DECIMAL(3,2),
    extraction_method VARCHAR(50),
    extracted_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        co.field_name,
        co.field_value,
        co.value_type,
        co.confidence,
        co.extraction_method,
        co.extracted_at
    FROM candidate_observations co
    WHERE co.candidate_id = p_candidate_id
      AND co.is_current = TRUE
    ORDER BY co.field_name, co.confidence DESC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 7. HELPER FUNCTION: Get recent activity for a candidate
-- =============================================================================
CREATE OR REPLACE FUNCTION get_candidate_recent_activity(
    p_candidate_id UUID,
    p_limit INT DEFAULT 50
)
RETURNS TABLE (
    event_id UUID,
    event_type VARCHAR(100),
    user_id UUID,
    event_data JSONB,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cae.id as event_id,
        cae.event_type,
        cae.user_id,
        cae.event_data,
        cae.created_at
    FROM candidate_activity_events cae
    WHERE cae.candidate_id = p_candidate_id
    ORDER BY cae.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 8. TRIGGER: Update updated_at timestamps
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to candidate_emails
DROP TRIGGER IF EXISTS update_candidate_emails_updated_at ON candidate_emails;
CREATE TRIGGER update_candidate_emails_updated_at
    BEFORE UPDATE ON candidate_emails
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to candidate_observations
DROP TRIGGER IF EXISTS update_candidate_observations_updated_at ON candidate_observations;
CREATE TRIGGER update_candidate_observations_updated_at
    BEFORE UPDATE ON candidate_observations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Done!
-- =============================================================================
SELECT 'Candidate observations tables created successfully!' as status;

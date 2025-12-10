-- Sprint 9: Scorecards, Interview Kits, Comments, Red Flags, Offer Declines
-- Run this migration in Supabase SQL Editor
-- NOTE: This version removes foreign key constraints for flexibility

-- =============================================================================
-- SCORECARD TEMPLATES
-- Admin-configurable rating attributes per interview stage
-- =============================================================================

CREATE TABLE IF NOT EXISTS scorecard_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    requisition_id UUID,
    name VARCHAR(200) NOT NULL,
    stage_name VARCHAR(100) NOT NULL,
    description TEXT,
    attributes JSONB NOT NULL DEFAULT '[]',
    interview_questions JSONB,
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for scorecard_templates
CREATE INDEX IF NOT EXISTS idx_scorecard_templates_tenant ON scorecard_templates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_scorecard_templates_requisition ON scorecard_templates(requisition_id);
CREATE INDEX IF NOT EXISTS idx_scorecard_templates_stage ON scorecard_templates(tenant_id, stage_name);
CREATE INDEX IF NOT EXISTS idx_scorecard_templates_active ON scorecard_templates(tenant_id, is_active);


-- =============================================================================
-- INTERVIEW FEEDBACK
-- Individual interviewer feedback with ratings
-- =============================================================================

CREATE TABLE IF NOT EXISTS interview_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    application_id UUID NOT NULL,
    template_id UUID,
    stage_name VARCHAR(100) NOT NULL,
    interviewer_id UUID NOT NULL,
    ratings JSONB NOT NULL DEFAULT '[]',
    overall_recommendation VARCHAR(50) NOT NULL,
    strengths JSONB,
    concerns JSONB,
    notes TEXT,
    is_submitted BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_recommendation CHECK (
        overall_recommendation IN ('strong_yes', 'yes', 'no', 'strong_no', 'needs_more_info')
    )
);

-- Indexes for interview_feedback
CREATE INDEX IF NOT EXISTS idx_interview_feedback_tenant ON interview_feedback(tenant_id);
CREATE INDEX IF NOT EXISTS idx_interview_feedback_application ON interview_feedback(application_id);
CREATE INDEX IF NOT EXISTS idx_interview_feedback_interviewer ON interview_feedback(interviewer_id);
CREATE INDEX IF NOT EXISTS idx_interview_feedback_stage ON interview_feedback(application_id, stage_name);
CREATE INDEX IF NOT EXISTS idx_interview_feedback_submitted ON interview_feedback(application_id, is_submitted);


-- =============================================================================
-- CANDIDATE COMMENTS
-- Threaded comments with @mentions on candidate profiles
-- =============================================================================

CREATE TABLE IF NOT EXISTS candidate_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    author_id UUID NOT NULL,
    content TEXT NOT NULL,
    mentions UUID[],
    parent_id UUID,
    is_edited BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for candidate_comments
CREATE INDEX IF NOT EXISTS idx_candidate_comments_tenant ON candidate_comments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidate_comments_candidate ON candidate_comments(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_comments_author ON candidate_comments(author_id);
CREATE INDEX IF NOT EXISTS idx_candidate_comments_parent ON candidate_comments(parent_id);
CREATE INDEX IF NOT EXISTS idx_candidate_comments_mentions ON candidate_comments USING GIN(mentions);


-- =============================================================================
-- CANDIDATE RED FLAGS
-- Risk management flags for candidates
-- =============================================================================

CREATE TABLE IF NOT EXISTS candidate_red_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    flag_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL,
    is_blocking BOOLEAN NOT NULL DEFAULT FALSE,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    expiration_date DATE,
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_severity CHECK (severity IN ('low', 'medium', 'high'))
);

-- Indexes for candidate_red_flags
CREATE INDEX IF NOT EXISTS idx_red_flags_tenant ON candidate_red_flags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_red_flags_candidate ON candidate_red_flags(candidate_id);
CREATE INDEX IF NOT EXISTS idx_red_flags_type ON candidate_red_flags(tenant_id, flag_type);
CREATE INDEX IF NOT EXISTS idx_red_flags_blocking ON candidate_red_flags(candidate_id, is_blocking, is_resolved);
CREATE INDEX IF NOT EXISTS idx_red_flags_resolved ON candidate_red_flags(tenant_id, is_resolved);


-- =============================================================================
-- OFFER DECLINE REASONS
-- Track why candidates decline offers for analytics
-- =============================================================================

CREATE TABLE IF NOT EXISTS offer_decline_reasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    offer_id UUID NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    secondary_reason_code VARCHAR(50),
    notes TEXT,
    competing_company VARCHAR(200),
    competing_salary DECIMAL(12,2),
    would_consider_future BOOLEAN DEFAULT FALSE,
    follow_up_date DATE,
    recorded_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_offer_decline UNIQUE(offer_id)
);

-- Indexes for offer_decline_reasons
CREATE INDEX IF NOT EXISTS idx_offer_decline_tenant ON offer_decline_reasons(tenant_id);
CREATE INDEX IF NOT EXISTS idx_offer_decline_offer ON offer_decline_reasons(offer_id);
CREATE INDEX IF NOT EXISTS idx_offer_decline_reason ON offer_decline_reasons(tenant_id, reason_code);
CREATE INDEX IF NOT EXISTS idx_offer_decline_future ON offer_decline_reasons(tenant_id, would_consider_future);
CREATE INDEX IF NOT EXISTS idx_offer_decline_date ON offer_decline_reasons(tenant_id, created_at);


-- =============================================================================
-- GRANTS for service role (Supabase)
-- =============================================================================

GRANT ALL ON scorecard_templates TO service_role;
GRANT ALL ON interview_feedback TO service_role;
GRANT ALL ON candidate_comments TO service_role;
GRANT ALL ON candidate_red_flags TO service_role;
GRANT ALL ON offer_decline_reasons TO service_role;

GRANT ALL ON scorecard_templates TO anon;
GRANT ALL ON interview_feedback TO anon;
GRANT ALL ON candidate_comments TO anon;
GRANT ALL ON candidate_red_flags TO anon;
GRANT ALL ON offer_decline_reasons TO anon;

GRANT ALL ON scorecard_templates TO authenticated;
GRANT ALL ON interview_feedback TO authenticated;
GRANT ALL ON candidate_comments TO authenticated;
GRANT ALL ON candidate_red_flags TO authenticated;
GRANT ALL ON offer_decline_reasons TO authenticated;


-- =============================================================================
-- UPDATED_AT TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers (IF NOT EXISTS not available for triggers, use DROP IF EXISTS)
DROP TRIGGER IF EXISTS update_scorecard_templates_updated_at ON scorecard_templates;
CREATE TRIGGER update_scorecard_templates_updated_at
    BEFORE UPDATE ON scorecard_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_interview_feedback_updated_at ON interview_feedback;
CREATE TRIGGER update_interview_feedback_updated_at
    BEFORE UPDATE ON interview_feedback
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_candidate_comments_updated_at ON candidate_comments;
CREATE TRIGGER update_candidate_comments_updated_at
    BEFORE UPDATE ON candidate_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_candidate_red_flags_updated_at ON candidate_red_flags;
CREATE TRIGGER update_candidate_red_flags_updated_at
    BEFORE UPDATE ON candidate_red_flags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =============================================================================
-- COMMENTS
-- =============================================================================
COMMENT ON TABLE scorecard_templates IS 'Admin-configurable interview scorecard templates with rating attributes';
COMMENT ON TABLE interview_feedback IS 'Individual interviewer feedback with structured ratings';
COMMENT ON TABLE candidate_comments IS 'Threaded comments with @mentions on candidate profiles';
COMMENT ON TABLE candidate_red_flags IS 'Risk management flags for candidates (do not rehire, etc.)';
COMMENT ON TABLE offer_decline_reasons IS 'Track why candidates decline offers for analytics';

-- ============================================================================
-- SPRINT 9 FIX: Clean creation of all tables without foreign key constraints
-- Run this in Supabase SQL Editor
-- ============================================================================

-- First, drop any partially created tables from previous attempts
DROP TABLE IF EXISTS offer_decline_reasons CASCADE;
DROP TABLE IF EXISTS candidate_red_flags CASCADE;
DROP TABLE IF EXISTS candidate_comments CASCADE;
DROP TABLE IF EXISTS interview_feedback CASCADE;
DROP TABLE IF EXISTS scorecard_templates CASCADE;

-- Also fix the eeo_responses table if it has issues
DROP TABLE IF EXISTS eeo_responses CASCADE;

-- ============================================================================
-- SCORECARD TEMPLATES
-- ============================================================================

CREATE TABLE scorecard_templates (
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

CREATE INDEX idx_scorecard_templates_tenant ON scorecard_templates(tenant_id);
CREATE INDEX idx_scorecard_templates_requisition ON scorecard_templates(requisition_id);
CREATE INDEX idx_scorecard_templates_stage ON scorecard_templates(tenant_id, stage_name);

-- ============================================================================
-- INTERVIEW FEEDBACK
-- ============================================================================

CREATE TABLE interview_feedback (
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
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_interview_feedback_tenant ON interview_feedback(tenant_id);
CREATE INDEX idx_interview_feedback_application ON interview_feedback(application_id);
CREATE INDEX idx_interview_feedback_interviewer ON interview_feedback(interviewer_id);

-- ============================================================================
-- CANDIDATE COMMENTS
-- ============================================================================

CREATE TABLE candidate_comments (
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

CREATE INDEX idx_candidate_comments_tenant ON candidate_comments(tenant_id);
CREATE INDEX idx_candidate_comments_candidate ON candidate_comments(candidate_id);
CREATE INDEX idx_candidate_comments_author ON candidate_comments(author_id);
CREATE INDEX idx_candidate_comments_parent ON candidate_comments(parent_id);

-- ============================================================================
-- CANDIDATE RED FLAGS
-- ============================================================================

CREATE TABLE candidate_red_flags (
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
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_red_flags_tenant ON candidate_red_flags(tenant_id);
CREATE INDEX idx_red_flags_candidate ON candidate_red_flags(candidate_id);
CREATE INDEX idx_red_flags_blocking ON candidate_red_flags(candidate_id, is_blocking, is_resolved);

-- ============================================================================
-- OFFER DECLINE REASONS
-- ============================================================================

CREATE TABLE offer_decline_reasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    offer_id UUID NOT NULL UNIQUE,
    reason_code VARCHAR(50) NOT NULL,
    secondary_reason_code VARCHAR(50),
    notes TEXT,
    competing_company VARCHAR(200),
    competing_salary DECIMAL(12,2),
    would_consider_future BOOLEAN DEFAULT FALSE,
    follow_up_date DATE,
    recorded_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_offer_decline_tenant ON offer_decline_reasons(tenant_id);
CREATE INDEX idx_offer_decline_offer ON offer_decline_reasons(offer_id);
CREATE INDEX idx_offer_decline_reason ON offer_decline_reasons(tenant_id, reason_code);

-- ============================================================================
-- EEO RESPONSES (recreate without FK)
-- ============================================================================

CREATE TABLE eeo_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    application_id UUID NOT NULL UNIQUE,
    gender VARCHAR(50),
    ethnicity VARCHAR(100),
    veteran_status VARCHAR(50),
    disability_status VARCHAR(50),
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_eeo_responses_tenant ON eeo_responses(tenant_id);
CREATE INDEX idx_eeo_responses_application ON eeo_responses(application_id);

-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT ALL ON scorecard_templates TO service_role, anon, authenticated;
GRANT ALL ON interview_feedback TO service_role, anon, authenticated;
GRANT ALL ON candidate_comments TO service_role, anon, authenticated;
GRANT ALL ON candidate_red_flags TO service_role, anon, authenticated;
GRANT ALL ON offer_decline_reasons TO service_role, anon, authenticated;
GRANT ALL ON eeo_responses TO service_role, anon, authenticated;

-- ============================================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_scorecard_templates_updated_at
    BEFORE UPDATE ON scorecard_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_interview_feedback_updated_at
    BEFORE UPDATE ON interview_feedback
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_candidate_comments_updated_at
    BEFORE UPDATE ON candidate_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_candidate_red_flags_updated_at
    BEFORE UPDATE ON candidate_red_flags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

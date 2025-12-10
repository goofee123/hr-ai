-- ====================================================================
-- Migration 001: Admin Configuration Tables
-- Enhanced Recruiting Module - Sprint 1
-- ====================================================================

-- ====================================================================
-- ADMIN CONFIGURATION TABLES
-- ====================================================================

-- Pipeline templates (configurable per tenant/client)
CREATE TABLE IF NOT EXISTS pipeline_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- stages format: [{"name": "Applied", "stage_type": "initial", "sort_order": 1, ...}]
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    UNIQUE(tenant_id, name)
);

-- Disposition reasons (rejection reasons)
CREATE TABLE IF NOT EXISTS disposition_reasons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    label VARCHAR(200) NOT NULL,
    description TEXT,
    is_eeo_compliant BOOLEAN DEFAULT TRUE,
    requires_notes BOOLEAN DEFAULT FALSE,
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

-- Application sources
CREATE TABLE IF NOT EXISTS application_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL DEFAULT 'other',
    -- source_type: 'job_board', 'referral', 'direct', 'agency', 'social', 'other'
    integration_config JSONB DEFAULT '{}'::jsonb,
    -- integration_config: API credentials, webhook URLs, etc.
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- SLA configuration per tenant
CREATE TABLE IF NOT EXISTS sla_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    job_type VARCHAR(50) NOT NULL DEFAULT 'standard',
    -- job_type: 'standard', 'executive', 'urgent', 'intern', 'contractor'
    job_sla_days INT NOT NULL DEFAULT 30,
    -- Days from opening to fill
    recruiter_sla_days INT NOT NULL DEFAULT 14,
    -- Days for recruiter to show progress
    amber_threshold_percent INT DEFAULT 75,
    -- Alert at 75% of SLA time elapsed
    red_threshold_percent INT DEFAULT 90,
    -- Critical at 90%
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- ====================================================================
-- SLA & ASSIGNMENT TABLES
-- ====================================================================

-- Recruiter assignments with separate SLA tracking
CREATE TABLE IF NOT EXISTS recruiter_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requisition_id UUID NOT NULL REFERENCES job_requisitions(id) ON DELETE CASCADE,
    recruiter_id UUID NOT NULL REFERENCES users(id),
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by UUID REFERENCES users(id),
    sla_days INT,
    sla_deadline TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    -- status: 'active', 'completed', 'reassigned'
    completed_at TIMESTAMPTZ,
    reassigned_to UUID REFERENCES users(id),
    reassigned_at TIMESTAMPTZ,
    reassignment_reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- SLA alerts and notifications
CREATE TABLE IF NOT EXISTS sla_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    alert_type VARCHAR(20) NOT NULL,
    -- alert_type: 'amber', 'red'
    entity_type VARCHAR(50) NOT NULL,
    -- entity_type: 'job_opening', 'recruiter_assignment'
    entity_id UUID NOT NULL,
    message TEXT,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ====================================================================
-- EEO COMPLIANCE TABLES
-- ====================================================================

-- EEO data collection (separate from candidate for privacy)
CREATE TABLE IF NOT EXISTS eeo_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    application_id UUID NOT NULL,
    gender VARCHAR(50),
    ethnicity VARCHAR(100),
    veteran_status VARCHAR(50),
    disability_status VARCHAR(50),
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(application_id)
);

-- Compliance audit trail
CREATE TABLE IF NOT EXISTS compliance_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    action_type VARCHAR(100) NOT NULL,
    -- action_type: 'stage_change', 'rejection', 'offer', 'hire', etc.
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    user_id UUID REFERENCES users(id),
    action_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ====================================================================
-- ALTER EXISTING TABLES
-- ====================================================================

-- Add SLA and source fields to job_requisitions
ALTER TABLE job_requisitions
ADD COLUMN IF NOT EXISTS dayforce_job_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS job_sla_days INT,
ADD COLUMN IF NOT EXISTS job_sla_deadline TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS job_opened_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS compensation_band_min DECIMAL(12,2),
ADD COLUMN IF NOT EXISTS compensation_band_max DECIMAL(12,2);

-- Add source and disposition fields to applications
ALTER TABLE applications
ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES application_sources(id),
ADD COLUMN IF NOT EXISTS cover_letter_text TEXT,
ADD COLUMN IF NOT EXISTS cover_letter_parsed JSONB,
ADD COLUMN IF NOT EXISTS eeo_consent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS disposition_reason_id UUID REFERENCES disposition_reasons(id),
ADD COLUMN IF NOT EXISTS disposition_notes TEXT;

-- Add parsed data fields to candidates
ALTER TABLE candidates
ADD COLUMN IF NOT EXISTS linkedin_url TEXT,
ADD COLUMN IF NOT EXISTS parsed_data JSONB,
ADD COLUMN IF NOT EXISTS skills_extracted TEXT[],
ADD COLUMN IF NOT EXISTS experience_years DECIMAL(4,1),
ADD COLUMN IF NOT EXISTS current_company TEXT,
ADD COLUMN IF NOT EXISTS current_title TEXT;

-- ====================================================================
-- INDEXES
-- ====================================================================

CREATE INDEX IF NOT EXISTS idx_pipeline_templates_tenant ON pipeline_templates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_disposition_reasons_tenant ON disposition_reasons(tenant_id);
CREATE INDEX IF NOT EXISTS idx_application_sources_tenant ON application_sources(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sla_configurations_tenant ON sla_configurations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_assignments_requisition ON recruiter_assignments(requisition_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_assignments_recruiter ON recruiter_assignments(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_sla_alerts_entity ON sla_alerts(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_compliance_audit_entity ON compliance_audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_compliance_audit_user ON compliance_audit_log(user_id);

-- ====================================================================
-- DEFAULT DATA
-- ====================================================================

-- Note: Default data should be inserted for each tenant on tenant creation
-- This is a template for reference

-- Default pipeline template example (insert per tenant):
-- INSERT INTO pipeline_templates (tenant_id, name, description, is_default, stages)
-- VALUES (
--     '{{tenant_id}}',
--     'Standard Hiring Pipeline',
--     'Default hiring workflow for most positions',
--     true,
--     '[
--         {"name": "Applied", "stage_type": "initial", "sort_order": 1},
--         {"name": "Screening", "stage_type": "screen", "sort_order": 2},
--         {"name": "Phone Interview", "stage_type": "interview", "sort_order": 3, "interview_required": true},
--         {"name": "On-site Interview", "stage_type": "interview", "sort_order": 4, "interview_required": true, "requires_feedback": true},
--         {"name": "Offer", "stage_type": "offer", "sort_order": 5},
--         {"name": "Hired", "stage_type": "hired", "sort_order": 6}
--     ]'::jsonb
-- );

-- Default disposition reasons example (insert per tenant):
-- INSERT INTO disposition_reasons (tenant_id, code, label, is_eeo_compliant, sort_order)
-- VALUES
--     ('{{tenant_id}}', 'NOT_QUALIFIED', 'Does not meet minimum qualifications', true, 1),
--     ('{{tenant_id}}', 'BETTER_CANDIDATE', 'Position filled with better qualified candidate', true, 2),
--     ('{{tenant_id}}', 'WITHDREW', 'Candidate withdrew application', true, 3),
--     ('{{tenant_id}}', 'NO_SHOW', 'Candidate did not show for interview', true, 4),
--     ('{{tenant_id}}', 'SALARY_EXPECTATIONS', 'Salary expectations not aligned', true, 5),
--     ('{{tenant_id}}', 'POSITION_CLOSED', 'Position closed/cancelled', true, 6);

-- Default application sources example (insert per tenant):
-- INSERT INTO application_sources (tenant_id, name, source_type)
-- VALUES
--     ('{{tenant_id}}', 'LinkedIn', 'job_board'),
--     ('{{tenant_id}}', 'Indeed', 'job_board'),
--     ('{{tenant_id}}', 'Employee Referral', 'referral'),
--     ('{{tenant_id}}', 'Career Site', 'direct'),
--     ('{{tenant_id}}', 'Staffing Agency', 'agency'),
--     ('{{tenant_id}}', 'Dayforce', 'direct');

-- Default SLA configuration example (insert per tenant):
-- INSERT INTO sla_configurations (tenant_id, name, job_type, job_sla_days, recruiter_sla_days, is_default)
-- VALUES
--     ('{{tenant_id}}', 'Standard', 'standard', 30, 14, true),
--     ('{{tenant_id}}', 'Executive', 'executive', 60, 21, false),
--     ('{{tenant_id}}', 'Urgent', 'urgent', 14, 7, false);

-- ============================================================================
-- Candidate Portal Tables (Sprint 12)
-- ============================================================================

-- Tenant Settings - Stores feature toggles and configuration per tenant
CREATE TABLE IF NOT EXISTS tenant_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_portal JSONB DEFAULT '{
        "enabled": true,
        "allow_status_check": true,
        "allow_document_upload": true,
        "allow_interview_reschedule": true,
        "require_eeo_form": true
    }'::jsonb,
    calendar_integration JSONB DEFAULT '{
        "enabled": false,
        "google_calendar_enabled": false,
        "outlook_calendar_enabled": false,
        "auto_create_video_meeting": true
    }'::jsonb,
    notifications JSONB DEFAULT '{
        "send_candidate_status_emails": true,
        "send_interview_reminders": true,
        "reminder_hours_before": [24, 1],
        "send_offer_emails": true,
        "send_rejection_emails": false,
        "rejection_email_delay_hours": 48
    }'::jsonb,
    ai_features JSONB DEFAULT '{
        "resume_parsing_enabled": true,
        "candidate_matching_enabled": true,
        "skill_extraction_enabled": true,
        "auto_screen_candidates": false
    }'::jsonb,
    compliance JSONB DEFAULT '{
        "eeo_tracking_enabled": true,
        "audit_logging_enabled": true,
        "require_rejection_reason": true,
        "data_retention_days": 365
    }'::jsonb,
    custom_settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Magic Links for candidate portal access
CREATE TABLE IF NOT EXISTS candidate_portal_magic_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Portal Sessions - Active candidate sessions
CREATE TABLE IF NOT EXISTS candidate_portal_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    session_token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Candidate Documents - Documents uploaded by candidates
CREATE TABLE IF NOT EXISTS candidate_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    file_url TEXT,
    file_size_bytes INT,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending_upload',
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interview Reschedule Requests from candidates
CREATE TABLE IF NOT EXISTS interview_reschedule_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interview_id UUID NOT NULL REFERENCES interview_schedules(id) ON DELETE CASCADE,
    requested_by_candidate BOOLEAN DEFAULT FALSE,
    requested_by_user_id UUID REFERENCES users(id),
    reason TEXT NOT NULL,
    preferred_dates TEXT,
    status VARCHAR(50) DEFAULT 'submitted',
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add withdrawal fields to applications if not exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'applications' AND column_name = 'withdrawn_at'
    ) THEN
        ALTER TABLE applications ADD COLUMN withdrawn_at TIMESTAMPTZ;
        ALTER TABLE applications ADD COLUMN withdrawal_reason TEXT;
    END IF;
END
$$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tenant_settings_tenant ON tenant_settings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_portal_magic_links_token ON candidate_portal_magic_links(token);
CREATE INDEX IF NOT EXISTS idx_portal_magic_links_candidate ON candidate_portal_magic_links(candidate_id);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_token ON candidate_portal_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_candidate ON candidate_portal_sessions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_documents_candidate ON candidate_documents(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_documents_application ON candidate_documents(application_id);
CREATE INDEX IF NOT EXISTS idx_interview_reschedule_interview ON interview_reschedule_requests(interview_id);

-- Enable RLS
ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_portal_magic_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_portal_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_reschedule_requests ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY tenant_settings_tenant_isolation ON tenant_settings
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY portal_magic_links_tenant_isolation ON candidate_portal_magic_links
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY portal_sessions_tenant_isolation ON candidate_portal_sessions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY candidate_documents_tenant_isolation ON candidate_documents
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY reschedule_requests_tenant_isolation ON interview_reschedule_requests
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Updated_at triggers
DROP TRIGGER IF EXISTS update_tenant_settings_updated_at ON tenant_settings;
CREATE TRIGGER update_tenant_settings_updated_at
    BEFORE UPDATE ON tenant_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_candidate_documents_updated_at ON candidate_documents;
CREATE TRIGGER update_candidate_documents_updated_at
    BEFORE UPDATE ON candidate_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_interview_reschedule_updated_at ON interview_reschedule_requests;
CREATE TRIGGER update_interview_reschedule_updated_at
    BEFORE UPDATE ON interview_reschedule_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Clean up expired sessions job-friendly view
CREATE OR REPLACE VIEW expired_portal_sessions AS
SELECT id, session_token, candidate_id
FROM candidate_portal_sessions
WHERE expires_at < NOW();

-- Clean up expired magic links job-friendly view
CREATE OR REPLACE VIEW expired_portal_magic_links AS
SELECT id, token, candidate_id
FROM candidate_portal_magic_links
WHERE expires_at < NOW() AND is_used = FALSE;

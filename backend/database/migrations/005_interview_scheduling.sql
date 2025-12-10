-- ============================================================================
-- Interview Scheduling Tables (Sprint 11)
-- ============================================================================

-- Interview Requests - Initial request for interview scheduling
CREATE TABLE IF NOT EXISTS interview_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage_name VARCHAR(100) NOT NULL,
    interview_type VARCHAR(50) NOT NULL DEFAULT 'video',
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes INT NOT NULL DEFAULT 60,
    interviewer_ids UUID[] NOT NULL,
    preferred_date_range_start DATE,
    preferred_date_range_end DATE,
    location VARCHAR(255),
    video_link TEXT,
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending_slots',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interviewer Availability - Track availability submissions
CREATE TABLE IF NOT EXISTS interviewer_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interview_request_id UUID NOT NULL REFERENCES interview_requests(id) ON DELETE CASCADE,
    interviewer_id UUID NOT NULL REFERENCES users(id),
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    duration_minutes INT NOT NULL DEFAULT 60,
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    available_slots JSONB DEFAULT '[]',
    weekly_patterns JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ,
    notes TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Self-Scheduling Links - Magic links for candidate self-scheduling
CREATE TABLE IF NOT EXISTS self_scheduling_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interview_request_id UUID NOT NULL REFERENCES interview_requests(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    available_slots JSONB NOT NULL DEFAULT '[]',
    expires_at TIMESTAMPTZ,
    max_reschedules INT DEFAULT 2,
    reschedule_count INT DEFAULT 0,
    is_used BOOLEAN DEFAULT FALSE,
    selected_slot JSONB,
    custom_message TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interview Reminders - Scheduled reminder notifications
CREATE TABLE IF NOT EXISTS interview_reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interview_schedule_id UUID NOT NULL REFERENCES interview_schedules(id) ON DELETE CASCADE,
    recipient_type VARCHAR(50) NOT NULL DEFAULT 'candidate',
    recipient_email VARCHAR(255),
    hours_before INT NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add interview_request_id to existing interview_schedules table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interview_schedules' AND column_name = 'interview_request_id'
    ) THEN
        ALTER TABLE interview_schedules ADD COLUMN interview_request_id UUID REFERENCES interview_requests(id);
    END IF;
END
$$;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_interview_requests_tenant ON interview_requests(tenant_id);
CREATE INDEX IF NOT EXISTS idx_interview_requests_application ON interview_requests(application_id);
CREATE INDEX IF NOT EXISTS idx_interview_requests_status ON interview_requests(status);

CREATE INDEX IF NOT EXISTS idx_interviewer_availability_tenant ON interviewer_availability(tenant_id);
CREATE INDEX IF NOT EXISTS idx_interviewer_availability_request ON interviewer_availability(interview_request_id);
CREATE INDEX IF NOT EXISTS idx_interviewer_availability_interviewer ON interviewer_availability(interviewer_id);

CREATE INDEX IF NOT EXISTS idx_self_scheduling_links_token ON self_scheduling_links(token);
CREATE INDEX IF NOT EXISTS idx_self_scheduling_links_request ON self_scheduling_links(interview_request_id);

CREATE INDEX IF NOT EXISTS idx_interview_reminders_schedule ON interview_reminders(interview_schedule_id);
CREATE INDEX IF NOT EXISTS idx_interview_reminders_scheduled_for ON interview_reminders(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_interview_reminders_status ON interview_reminders(status);

-- Enable RLS
ALTER TABLE interview_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE interviewer_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE self_scheduling_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_reminders ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY interview_requests_tenant_isolation ON interview_requests
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY interviewer_availability_tenant_isolation ON interviewer_availability
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY self_scheduling_links_tenant_isolation ON self_scheduling_links
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY interview_reminders_tenant_isolation ON interview_reminders
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_interview_requests_updated_at ON interview_requests;
CREATE TRIGGER update_interview_requests_updated_at
    BEFORE UPDATE ON interview_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_interviewer_availability_updated_at ON interviewer_availability;
CREATE TRIGGER update_interviewer_availability_updated_at
    BEFORE UPDATE ON interviewer_availability
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_self_scheduling_links_updated_at ON self_scheduling_links;
CREATE TRIGGER update_self_scheduling_links_updated_at
    BEFORE UPDATE ON self_scheduling_links
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

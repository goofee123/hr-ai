-- ====================================================================
-- HRM-Core Database Schema
-- Unified HR Platform - Recruiting & Compensation Management
-- PostgreSQL + Supabase
-- ====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ====================================================================
-- ENUMS
-- ====================================================================

-- User Roles
CREATE TYPE user_role AS ENUM (
    'super_admin',
    'hr_admin',
    'recruiter',
    'hiring_manager',
    'compensation_analyst',
    'executive',
    'payroll',
    'employee'
);

-- Requisition Status
CREATE TYPE requisition_status AS ENUM (
    'draft',
    'pending_approval',
    'open',
    'on_hold',
    'closed_filled',
    'closed_cancelled'
);

-- Application Status
CREATE TYPE application_status AS ENUM (
    'new',
    'in_review',
    'interviewing',
    'offer_pending',
    'offer_extended',
    'offer_accepted',
    'offer_declined',
    'hired',
    'rejected',
    'withdrawn'
);

-- Candidate Source
CREATE TYPE candidate_source AS ENUM (
    'linkedin',
    'indeed',
    'glassdoor',
    'referral',
    'agency',
    'career_site',
    'walk_in',
    'university',
    'internal',
    'other'
);

-- Worker Type
CREATE TYPE worker_type AS ENUM (
    'full_time',
    'part_time',
    'contractor',
    'intern',
    'temp',
    'seasonal'
);

-- Task Status
CREATE TYPE task_status AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'cancelled',
    'snoozed'
);

-- Task Priority
CREATE TYPE task_priority AS ENUM (
    'low',
    'normal',
    'high',
    'urgent'
);

-- Offer Status
CREATE TYPE offer_status AS ENUM (
    'draft',
    'pending_approval',
    'approved',
    'sent',
    'viewed',
    'accepted',
    'declined',
    'expired',
    'rescinded'
);

-- Comp Cycle Type
CREATE TYPE comp_cycle_type AS ENUM (
    'annual',
    'mid_year',
    'off_cycle',
    'promotion',
    'market_adjustment'
);

-- Comp Cycle Status
CREATE TYPE comp_cycle_status AS ENUM (
    'draft',
    'configuration',
    'data_import',
    'calculation',
    'manager_input',
    'hr_review',
    'executive_approval',
    'finalization',
    'export',
    'completed',
    'archived'
);

-- Comp Rule Action Type
CREATE TYPE comp_rule_action AS ENUM (
    'SET_RECOMMENDED_INCREASE_PERCENT',
    'SET_RECOMMENDED_INCREASE_AMOUNT',
    'CAP_INCREASE_PERCENT',
    'CAP_INCREASE_AMOUNT',
    'FLAG_FOR_REVIEW',
    'REQUIRE_APPROVAL',
    'SET_BONUS_PERCENT',
    'CAP_BONUS',
    'EXCLUDE_FROM_CYCLE',
    'SET_MINIMUM_INCREASE',
    'APPLY_MULTIPLIER'
);

-- Decision Status
CREATE TYPE decision_status AS ENUM (
    'pending',
    'manager_submitted',
    'hr_approved',
    'hr_modified',
    'hr_rejected',
    'final',
    'exported'
);

-- ====================================================================
-- FOUNDATION TABLES
-- ====================================================================

-- Tenants (Organizations)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    logo_url TEXT,
    settings JSONB DEFAULT '{}'::jsonb,
    dayforce_config JSONB DEFAULT '{}'::jsonb,
    halogen_config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'employee',
    employee_id VARCHAR(50),
    department_id UUID,
    avatar_url TEXT,
    phone VARCHAR(50),
    preferences JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

-- Departments
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES departments(id),
    manager_id UUID REFERENCES users(id),
    cost_center VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

-- Add FK from users to departments
ALTER TABLE users ADD CONSTRAINT fk_users_department
    FOREIGN KEY (department_id) REFERENCES departments(id);

-- Locations
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    address JSONB,
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    is_remote BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

-- Pay Grades
CREATE TABLE pay_grades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100),
    min_hourly DECIMAL(10,4),
    mid_hourly DECIMAL(10,4),
    max_hourly DECIMAL(10,4),
    min_annual DECIMAL(12,2),
    mid_annual DECIMAL(12,2),
    max_annual DECIMAL(12,2),
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    effective_date DATE,
    expiry_date DATE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code, effective_date)
);

-- Internal Job Titles
CREATE TABLE internal_job_titles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    job_family VARCHAR(100),
    default_pay_grade_id UUID REFERENCES pay_grades(id),
    flsa_status VARCHAR(20) CHECK (flsa_status IN ('exempt', 'non_exempt')),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

-- ====================================================================
-- RECRUITING TABLES
-- ====================================================================

-- Requisition Templates (Pipeline configurations)
CREATE TABLE requisition_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    pipeline_stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    default_sla_days INT DEFAULT 30,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Job Requisitions
CREATE TABLE job_requisitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requisition_number VARCHAR(50) NOT NULL,

    -- Job Details
    internal_title_id UUID REFERENCES internal_job_titles(id),
    internal_title VARCHAR(255),
    external_title VARCHAR(255) NOT NULL,
    job_description TEXT,
    requirements TEXT,

    -- Organization
    department_id UUID REFERENCES departments(id),
    location_id UUID REFERENCES locations(id),
    reports_to_id UUID REFERENCES users(id),

    -- Compensation
    pay_grade_id UUID REFERENCES pay_grades(id),
    salary_min DECIMAL(12,2),
    salary_max DECIMAL(12,2),
    target_salary DECIMAL(12,2),
    is_salary_visible BOOLEAN DEFAULT FALSE,

    -- Headcount
    positions_approved INT DEFAULT 1,
    positions_filled INT DEFAULT 0,
    worker_type worker_type DEFAULT 'full_time',

    -- Workflow
    status requisition_status DEFAULT 'draft',
    template_id UUID REFERENCES requisition_templates(id),
    pipeline_stages JSONB,

    -- Assignment
    primary_recruiter_id UUID REFERENCES users(id),
    hiring_manager_id UUID REFERENCES users(id),

    -- SLA Tracking
    target_fill_date DATE,
    sla_days INT DEFAULT 45,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,

    -- Approvals
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    -- Posting
    is_posted_internal BOOLEAN DEFAULT FALSE,
    is_posted_external BOOLEAN DEFAULT FALSE,
    posting_urls JSONB DEFAULT '{}'::jsonb,

    metadata JSONB DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, requisition_number)
);

-- Candidates
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Contact Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    linkedin_url TEXT,
    location JSONB,

    -- Source
    source candidate_source,
    source_detail VARCHAR(255),
    referred_by_id UUID REFERENCES users(id),

    -- Classification
    worker_type_preference worker_type,
    is_internal_candidate BOOLEAN DEFAULT FALSE,
    current_employee_id UUID REFERENCES users(id),

    -- Tags/Skills
    skills TEXT[],
    tags TEXT[],

    -- Privacy
    is_do_not_contact BOOLEAN DEFAULT FALSE,
    gdpr_consent_at TIMESTAMPTZ,
    gdpr_expiry_at TIMESTAMPTZ,

    -- Aggregates
    total_applications INT DEFAULT 0,

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

-- Resumes
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,

    -- File Storage
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),

    -- Parsed Data
    raw_text TEXT,
    parsed_data JSONB DEFAULT '{}'::jsonb,

    -- Versioning
    version_number INT DEFAULT 1,
    is_primary BOOLEAN DEFAULT FALSE,

    -- Parsing Status
    parsing_status VARCHAR(50) DEFAULT 'pending',
    parsed_at TIMESTAMPTZ,

    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline Stages (per requisition)
CREATE TABLE pipeline_stages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requisition_id UUID NOT NULL REFERENCES job_requisitions(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    stage_type VARCHAR(50) DEFAULT 'standard',
    sort_order INT NOT NULL,

    -- Stage Config
    is_rejection_stage BOOLEAN DEFAULT FALSE,
    auto_advance_days INT,
    requires_feedback BOOLEAN DEFAULT FALSE,
    interview_required BOOLEAN DEFAULT FALSE,

    -- Counts
    candidate_count INT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(requisition_id, sort_order)
);

-- Applications
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    requisition_id UUID NOT NULL REFERENCES job_requisitions(id) ON DELETE CASCADE,

    -- Status
    status application_status DEFAULT 'new',
    current_stage VARCHAR(100) DEFAULT 'Applied',
    current_stage_id UUID REFERENCES pipeline_stages(id),
    stage_entered_at TIMESTAMPTZ DEFAULT NOW(),

    -- Resume
    resume_id UUID REFERENCES resumes(id),
    cover_letter TEXT,

    -- Screening
    screening_answers JSONB DEFAULT '{}'::jsonb,

    -- Scores
    recruiter_rating INT CHECK (recruiter_rating BETWEEN 1 AND 5),
    hiring_manager_rating INT CHECK (hiring_manager_rating BETWEEN 1 AND 5),
    overall_score DECIMAL(5,2),

    -- Rejection
    rejection_reason VARCHAR(255),
    rejection_notes TEXT,
    rejected_by UUID REFERENCES users(id),
    rejected_at TIMESTAMPTZ,

    -- Offer
    offer_id UUID,

    -- Assignment
    assigned_recruiter_id UUID REFERENCES users(id),

    -- Timing
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),

    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(candidate_id, requisition_id)
);

-- Application Events (Audit Trail)
CREATE TABLE application_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Event Details
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Actor
    performed_by UUID REFERENCES users(id),
    performed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Visibility
    is_internal BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interview Schedules
CREATE TABLE interview_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Interview Details
    interview_type VARCHAR(50),
    title VARCHAR(255),
    description TEXT,

    -- Scheduling
    scheduled_at TIMESTAMPTZ,
    duration_minutes INT DEFAULT 60,
    timezone VARCHAR(50),
    location VARCHAR(255),
    video_link TEXT,

    -- Participants
    interviewer_ids UUID[],
    organizer_id UUID REFERENCES users(id),

    -- Status
    status VARCHAR(50) DEFAULT 'scheduled',

    -- Feedback
    feedback_due_by TIMESTAMPTZ,
    all_feedback_received BOOLEAN DEFAULT FALSE,

    -- Calendar
    calendar_event_id VARCHAR(255),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interview Feedback
CREATE TABLE interview_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    interview_id UUID NOT NULL REFERENCES interview_schedules(id) ON DELETE CASCADE,

    interviewer_id UUID NOT NULL REFERENCES users(id),

    -- Ratings
    overall_rating INT CHECK (overall_rating BETWEEN 1 AND 5),
    recommendation VARCHAR(50),
    ratings_by_competency JSONB DEFAULT '{}'::jsonb,

    -- Feedback
    strengths TEXT,
    concerns TEXT,
    notes TEXT,

    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Recruiter Tasks
CREATE TABLE recruiter_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Context
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    requisition_id UUID REFERENCES job_requisitions(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,

    -- Task Details
    task_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Assignment
    assigned_to UUID REFERENCES users(id),

    -- Due Date
    due_date DATE,
    priority task_priority DEFAULT 'normal',

    -- Status
    status task_status DEFAULT 'pending',
    completed_at TIMESTAMPTZ,
    completed_by UUID REFERENCES users(id),

    -- Reminders
    reminder_sent BOOLEAN DEFAULT FALSE,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Offers
CREATE TABLE offers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Compensation
    offer_type VARCHAR(50),
    base_salary DECIMAL(12,2),
    pay_frequency VARCHAR(20),
    bonus_percent DECIMAL(5,2),
    sign_on_bonus DECIMAL(12,2),
    equity_shares INT,

    -- Job Details
    job_title VARCHAR(255),
    department_id UUID REFERENCES departments(id),
    location_id UUID REFERENCES locations(id),
    start_date DATE,

    -- Status
    status offer_status DEFAULT 'draft',

    -- Approvals
    requires_approval BOOLEAN DEFAULT TRUE,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    -- Sending
    sent_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    -- Response
    responded_at TIMESTAMPTZ,
    decline_reason TEXT,

    -- Letter
    offer_letter_path TEXT,
    signed_letter_path TEXT,

    version INT DEFAULT 1,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add FK from applications to offers
ALTER TABLE applications ADD CONSTRAINT fk_applications_offer
    FOREIGN KEY (offer_id) REFERENCES offers(id);

-- ====================================================================
-- COMPENSATION TABLES
-- ====================================================================

-- Compensation Dataset Versions
CREATE TABLE comp_dataset_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Version Info
    version_number INT NOT NULL,
    version_name VARCHAR(100),
    description TEXT,

    -- Source
    source_system VARCHAR(50) DEFAULT 'dayforce',
    import_file_path TEXT,
    import_file_hash VARCHAR(64),

    -- Stats
    employee_count INT DEFAULT 0,
    import_errors JSONB DEFAULT '[]'::jsonb,

    -- Status
    status VARCHAR(50) DEFAULT 'importing',
    is_current BOOLEAN DEFAULT FALSE,

    -- Audit
    imported_by UUID REFERENCES users(id),
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    validated_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, version_number)
);

-- Employee Compensation Snapshots
CREATE TABLE employee_comp_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES comp_dataset_versions(id) ON DELETE CASCADE,

    -- Employee Identity
    employee_id VARCHAR(50) NOT NULL,
    employee_number VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),

    -- Position
    job_title VARCHAR(255),
    job_code VARCHAR(50),
    job_title_id UUID REFERENCES internal_job_titles(id),
    department_code VARCHAR(50),
    department_name VARCHAR(255),
    department_id UUID REFERENCES departments(id),
    location_code VARCHAR(50),
    location_id UUID REFERENCES locations(id),
    cost_center VARCHAR(50),

    -- Manager
    manager_employee_id VARCHAR(50),
    manager_name VARCHAR(255),
    manager_user_id UUID REFERENCES users(id),

    -- Employment
    hire_date DATE,
    original_hire_date DATE,
    job_start_date DATE,
    flsa_status VARCHAR(20),
    worker_type worker_type,
    employment_status VARCHAR(50),

    -- Current Compensation
    pay_grade_code VARCHAR(50),
    pay_grade_id UUID REFERENCES pay_grades(id),
    current_hourly_rate DECIMAL(10,4),
    current_weekly_rate DECIMAL(12,2),
    current_annual_salary DECIMAL(12,2),
    standard_hours DECIMAL(5,2) DEFAULT 40,

    -- Comp Metrics
    compa_ratio DECIMAL(5,4),
    range_penetration DECIMAL(5,4),

    -- Historical
    last_increase_date DATE,
    last_increase_percent DECIMAL(5,2),
    years_in_role DECIMAL(4,2),
    years_of_service DECIMAL(4,2),

    -- Bonus/Overtime
    ot_hours_ytd DECIMAL(8,2) DEFAULT 0,
    ot_earnings_ytd DECIMAL(12,2) DEFAULT 0,
    bonus_ytd DECIMAL(12,2) DEFAULT 0,

    -- Eligibility
    is_bonus_eligible BOOLEAN DEFAULT TRUE,
    is_increase_eligible BOOLEAN DEFAULT TRUE,
    is_gbb_eligible BOOLEAN DEFAULT FALSE,
    is_cap_bonus_eligible BOOLEAN DEFAULT FALSE,

    -- Performance
    performance_rating VARCHAR(50),
    performance_score DECIMAL(5,2),
    performance_review_date DATE,

    -- Metadata
    raw_import_data JSONB,
    validation_errors JSONB DEFAULT '[]'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dataset_version_id, employee_id)
);

-- Compensation Rule Sets
CREATE TABLE comp_rule_sets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    description TEXT,
    style VARCHAR(50),

    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Compensation Rules
CREATE TABLE comp_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rule_set_id UUID NOT NULL REFERENCES comp_rule_sets(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Execution Order
    priority INT DEFAULT 100,

    -- Condition (JSON expression)
    condition_expression JSONB NOT NULL,

    -- Action
    action comp_rule_action NOT NULL,
    action_value DECIMAL(10,4),
    action_params JSONB DEFAULT '{}'::jsonb,

    -- Flags
    is_active BOOLEAN DEFAULT TRUE,
    stop_processing BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Compensation Scenarios
CREATE TABLE comp_scenarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Inputs
    dataset_version_id UUID NOT NULL REFERENCES comp_dataset_versions(id),
    rule_set_id UUID NOT NULL REFERENCES comp_rule_sets(id),

    -- Parameters
    budget_percent DECIMAL(5,2),
    budget_amount DECIMAL(14,2),
    effective_date DATE,

    -- Status
    status VARCHAR(50) DEFAULT 'draft',

    -- Calculations
    calculated_at TIMESTAMPTZ,
    calculated_by UUID REFERENCES users(id),

    -- Results Summary
    total_current_payroll DECIMAL(14,2),
    total_recommended_payroll DECIMAL(14,2),
    total_increase_amount DECIMAL(14,2),
    total_increase_percent DECIMAL(5,2),
    employee_count INT,
    flagged_count INT,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scenario Employee Results
CREATE TABLE comp_scenario_employee_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scenario_id UUID NOT NULL REFERENCES comp_scenarios(id) ON DELETE CASCADE,
    employee_snapshot_id UUID NOT NULL REFERENCES employee_comp_snapshots(id),

    -- Employee Reference
    employee_id VARCHAR(50),
    employee_name VARCHAR(255),
    department_name VARCHAR(255),
    job_title VARCHAR(255),

    -- Current
    current_annual_salary DECIMAL(12,2),
    current_compa_ratio DECIMAL(5,4),

    -- Recommendations
    recommended_increase_percent DECIMAL(5,2),
    recommended_increase_amount DECIMAL(12,2),
    recommended_new_salary DECIMAL(12,2),
    recommended_new_compa_ratio DECIMAL(5,4),

    -- Bonus
    recommended_bonus_percent DECIMAL(5,2),
    recommended_bonus_amount DECIMAL(12,2),

    -- Rules Applied
    rules_applied JSONB DEFAULT '[]'::jsonb,

    -- Flags
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reasons TEXT[],
    requires_approval BOOLEAN DEFAULT FALSE,

    -- Notes
    system_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scenario_id, employee_snapshot_id)
);

-- Compensation Cycles
CREATE TABLE comp_cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    cycle_type comp_cycle_type NOT NULL,
    year INT NOT NULL,

    -- Scenario Selection
    selected_scenario_id UUID REFERENCES comp_scenarios(id),

    -- Timeline
    planning_start_date DATE,
    manager_input_start DATE,
    manager_input_deadline DATE,
    hr_review_deadline DATE,
    effective_date DATE,

    -- Budget
    total_budget_amount DECIMAL(14,2),
    allocated_amount DECIMAL(14,2),
    remaining_amount DECIMAL(14,2),

    -- Status
    status comp_cycle_status DEFAULT 'draft',

    -- Export
    last_export_at TIMESTAMPTZ,
    export_batch_id UUID,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, year, cycle_type)
);

-- Manager Compensation Inputs
CREATE TABLE manager_comp_inputs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,
    employee_result_id UUID NOT NULL REFERENCES comp_scenario_employee_results(id),

    -- Manager
    manager_id UUID NOT NULL REFERENCES users(id),

    -- Proposal
    proposed_increase_percent DECIMAL(5,2),
    proposed_increase_amount DECIMAL(12,2),
    proposed_bonus_percent DECIMAL(5,2),
    proposed_bonus_amount DECIMAL(12,2),

    -- Promotion
    is_promotion_request BOOLEAN DEFAULT FALSE,
    proposed_new_title VARCHAR(255),
    proposed_new_grade_id UUID REFERENCES pay_grades(id),
    promotion_justification TEXT,

    -- Comments
    manager_comments TEXT,

    -- Status
    status decision_status DEFAULT 'pending',
    submitted_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cycle_id, employee_result_id)
);

-- HR Compensation Decisions
CREATE TABLE hr_comp_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,
    manager_input_id UUID REFERENCES manager_comp_inputs(id),
    employee_result_id UUID NOT NULL REFERENCES comp_scenario_employee_results(id),

    -- HR Decision Maker
    decided_by UUID NOT NULL REFERENCES users(id),

    -- Final Decision
    final_increase_percent DECIMAL(5,2),
    final_increase_amount DECIMAL(12,2),
    final_new_salary DECIMAL(12,2),
    final_bonus_percent DECIMAL(5,2),
    final_bonus_amount DECIMAL(12,2),

    -- Promotion
    is_promotion_approved BOOLEAN,
    approved_new_title VARCHAR(255),
    approved_new_grade_id UUID REFERENCES pay_grades(id),

    -- Variance
    variance_from_recommendation DECIMAL(12,2),
    variance_reason TEXT,

    -- Comments
    hr_comments TEXT,

    -- Approval Chain
    requires_exec_approval BOOLEAN DEFAULT FALSE,
    exec_approved_by UUID REFERENCES users(id),
    exec_approved_at TIMESTAMPTZ,

    -- Status
    status decision_status DEFAULT 'pending',
    decided_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cycle_id, employee_result_id)
);

-- Compensation Export Batches
CREATE TABLE comp_export_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,

    batch_number INT NOT NULL,
    export_type VARCHAR(50) DEFAULT 'dayforce',

    -- File
    file_name VARCHAR(255),
    file_path TEXT,

    -- Stats
    record_count INT,
    total_increase_amount DECIMAL(14,2),
    total_bonus_amount DECIMAL(14,2),

    -- Status
    status VARCHAR(50) DEFAULT 'generated',

    -- Audit
    generated_by UUID REFERENCES users(id),
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,

    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cycle_id, batch_number)
);

-- ====================================================================
-- AUDIT LOG
-- ====================================================================

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,

    -- Actor
    user_id UUID REFERENCES users(id),
    user_email VARCHAR(255),
    user_role user_role,

    -- Action
    action VARCHAR(100) NOT NULL,

    -- Resource
    resource_type VARCHAR(100),
    resource_id UUID,

    -- Data
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Context
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ====================================================================
-- INDEXES
-- ====================================================================

-- Users
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(tenant_id, role);
CREATE INDEX idx_users_employee_id ON users(tenant_id, employee_id);

-- Departments
CREATE INDEX idx_departments_tenant ON departments(tenant_id);
CREATE INDEX idx_departments_parent ON departments(parent_id);

-- Locations
CREATE INDEX idx_locations_tenant ON locations(tenant_id);

-- Pay Grades
CREATE INDEX idx_pay_grades_tenant ON pay_grades(tenant_id);

-- Job Titles
CREATE INDEX idx_job_titles_tenant ON internal_job_titles(tenant_id);

-- Requisitions
CREATE INDEX idx_requisitions_tenant ON job_requisitions(tenant_id);
CREATE INDEX idx_requisitions_status ON job_requisitions(tenant_id, status);
CREATE INDEX idx_requisitions_recruiter ON job_requisitions(primary_recruiter_id);
CREATE INDEX idx_requisitions_hiring_mgr ON job_requisitions(hiring_manager_id);
CREATE INDEX idx_requisitions_department ON job_requisitions(department_id);

-- Candidates
CREATE INDEX idx_candidates_tenant ON candidates(tenant_id);
CREATE INDEX idx_candidates_email ON candidates(tenant_id, email);
CREATE INDEX idx_candidates_source ON candidates(tenant_id, source);
CREATE INDEX idx_candidates_skills ON candidates USING GIN(skills);
CREATE INDEX idx_candidates_tags ON candidates USING GIN(tags);

-- Resumes
CREATE INDEX idx_resumes_candidate ON resumes(candidate_id);

-- Pipeline Stages
CREATE INDEX idx_pipeline_stages_requisition ON pipeline_stages(requisition_id);

-- Applications
CREATE INDEX idx_applications_tenant ON applications(tenant_id);
CREATE INDEX idx_applications_candidate ON applications(candidate_id);
CREATE INDEX idx_applications_requisition ON applications(requisition_id);
CREATE INDEX idx_applications_status ON applications(tenant_id, status);
CREATE INDEX idx_applications_recruiter ON applications(assigned_recruiter_id);

-- Application Events
CREATE INDEX idx_app_events_application ON application_events(application_id);
CREATE INDEX idx_app_events_type ON application_events(tenant_id, event_type);

-- Interviews
CREATE INDEX idx_interviews_application ON interview_schedules(application_id);
CREATE INDEX idx_interviews_scheduled ON interview_schedules(scheduled_at);

-- Tasks
CREATE INDEX idx_tasks_tenant ON recruiter_tasks(tenant_id);
CREATE INDEX idx_tasks_assigned ON recruiter_tasks(assigned_to);
CREATE INDEX idx_tasks_status ON recruiter_tasks(tenant_id, status);

-- Offers
CREATE INDEX idx_offers_application ON offers(application_id);
CREATE INDEX idx_offers_status ON offers(tenant_id, status);

-- Comp Dataset Versions
CREATE INDEX idx_dataset_versions_tenant ON comp_dataset_versions(tenant_id);

-- Employee Snapshots
CREATE INDEX idx_emp_snapshots_version ON employee_comp_snapshots(dataset_version_id);
CREATE INDEX idx_emp_snapshots_employee ON employee_comp_snapshots(tenant_id, employee_id);
CREATE INDEX idx_emp_snapshots_manager ON employee_comp_snapshots(manager_employee_id);

-- Rule Sets
CREATE INDEX idx_rule_sets_tenant ON comp_rule_sets(tenant_id);

-- Rules
CREATE INDEX idx_rules_set ON comp_rules(rule_set_id);
CREATE INDEX idx_rules_priority ON comp_rules(rule_set_id, priority);

-- Scenarios
CREATE INDEX idx_scenarios_tenant ON comp_scenarios(tenant_id);
CREATE INDEX idx_scenarios_dataset ON comp_scenarios(dataset_version_id);

-- Scenario Results
CREATE INDEX idx_scenario_results_scenario ON comp_scenario_employee_results(scenario_id);

-- Cycles
CREATE INDEX idx_cycles_tenant ON comp_cycles(tenant_id);
CREATE INDEX idx_cycles_status ON comp_cycles(tenant_id, status);

-- Manager Inputs
CREATE INDEX idx_mgr_inputs_cycle ON manager_comp_inputs(cycle_id);
CREATE INDEX idx_mgr_inputs_manager ON manager_comp_inputs(manager_id);

-- HR Decisions
CREATE INDEX idx_hr_decisions_cycle ON hr_comp_decisions(cycle_id);

-- Audit Log
CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

-- ====================================================================
-- TRIGGERS
-- ====================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER update_tenants_timestamp BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_users_timestamp BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_departments_timestamp BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_locations_timestamp BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_pay_grades_timestamp BEFORE UPDATE ON pay_grades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_job_titles_timestamp BEFORE UPDATE ON internal_job_titles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_templates_timestamp BEFORE UPDATE ON requisition_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_requisitions_timestamp BEFORE UPDATE ON job_requisitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_candidates_timestamp BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_applications_timestamp BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_interviews_timestamp BEFORE UPDATE ON interview_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_tasks_timestamp BEFORE UPDATE ON recruiter_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_offers_timestamp BEFORE UPDATE ON offers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_rule_sets_timestamp BEFORE UPDATE ON comp_rule_sets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_rules_timestamp BEFORE UPDATE ON comp_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_scenarios_timestamp BEFORE UPDATE ON comp_scenarios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_cycles_timestamp BEFORE UPDATE ON comp_cycles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_mgr_inputs_timestamp BEFORE UPDATE ON manager_comp_inputs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_hr_decisions_timestamp BEFORE UPDATE ON hr_comp_decisions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-generate requisition number
CREATE OR REPLACE FUNCTION generate_requisition_number()
RETURNS TRIGGER AS $$
DECLARE
    next_num INT;
BEGIN
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(requisition_number FROM 'REQ-\d{4}-(\d+)') AS INT)
    ), 0) + 1
    INTO next_num
    FROM job_requisitions
    WHERE tenant_id = NEW.tenant_id
    AND requisition_number LIKE 'REQ-' || EXTRACT(YEAR FROM NOW())::TEXT || '-%';

    NEW.requisition_number := 'REQ-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' || LPAD(next_num::TEXT, 4, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_requisition_number BEFORE INSERT ON job_requisitions
    FOR EACH ROW WHEN (NEW.requisition_number IS NULL)
    EXECUTE FUNCTION generate_requisition_number();

-- Update candidate application count
CREATE OR REPLACE FUNCTION update_candidate_application_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE candidates SET total_applications = total_applications + 1
        WHERE id = NEW.candidate_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE candidates SET total_applications = total_applications - 1
        WHERE id = OLD.candidate_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_app_count AFTER INSERT OR DELETE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_candidate_application_count();

-- ====================================================================
-- ROW LEVEL SECURITY (RLS)
-- ====================================================================

-- Enable RLS on all tenant-scoped tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pay_grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE internal_job_titles ENABLE ROW LEVEL SECURITY;
ALTER TABLE requisition_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_requisitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE recruiter_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_dataset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_comp_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_rule_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_scenario_employee_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE manager_comp_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE hr_comp_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_export_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

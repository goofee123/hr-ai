-- =============================================================================
-- COMPENSATION MODULE FOUNDATION
-- Sprint 13-14: Rules-driven compensation planning system
-- =============================================================================

-- =============================================================================
-- COMPENSATION CYCLE MANAGEMENT
-- =============================================================================

-- Compensation cycles (annual planning events)
CREATE TABLE IF NOT EXISTS comp_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    fiscal_year INT NOT NULL,
    cycle_type VARCHAR(50) NOT NULL DEFAULT 'annual',

    -- Scheduling (flexible per department or company-wide)
    scope_type VARCHAR(50) DEFAULT 'company_wide',
    department_ids UUID[] DEFAULT '{}',

    -- Timeline
    effective_date DATE NOT NULL,
    planning_start_date DATE,
    manager_review_start DATE,
    manager_review_deadline DATE,
    executive_review_deadline DATE,

    -- Status: draft, modeling, manager_review, executive_review, comp_qa, approved, exported, archived
    status VARCHAR(50) DEFAULT 'draft',

    -- Budget constraints
    overall_budget_percent DECIMAL(5,2),
    budget_guidance TEXT,

    -- Metadata
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- EMPLOYEE COMPENSATION DATA (Versioned Snapshots)
-- =============================================================================

-- Dataset versions (each import creates a version)
CREATE TABLE IF NOT EXISTS comp_dataset_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID REFERENCES comp_cycles(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    source VARCHAR(100),
    source_file_name VARCHAR(255),

    -- Import metadata
    imported_by UUID REFERENCES users(id),
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    row_count INT,
    error_count INT DEFAULT 0,

    -- Status: imported, validated, active, archived
    status VARCHAR(50) DEFAULT 'imported',
    is_active BOOLEAN DEFAULT FALSE,

    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Employee compensation snapshots (one row per employee per dataset version)
CREATE TABLE IF NOT EXISTS comp_employee_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES comp_dataset_versions(id) ON DELETE CASCADE,

    -- Employee Identity (from Dayforce)
    employee_id VARCHAR(50) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),

    -- Organization
    business_unit VARCHAR(100),
    department VARCHAR(100),
    sub_department VARCHAR(100),
    manager_name VARCHAR(200),
    manager_employee_id VARCHAR(50),
    job_title VARCHAR(200),

    -- Employment Details
    hire_date DATE,
    last_increase_date DATE,
    employment_type VARCHAR(50),
    schedule VARCHAR(50),
    weekly_hours DECIMAL(5,2) DEFAULT 40,
    location VARCHAR(100),
    country VARCHAR(50),

    -- Current Compensation (from Dayforce - prior year data)
    current_hourly_rate DECIMAL(12,4),
    current_weekly DECIMAL(12,2),
    current_annual DECIMAL(12,2),

    -- Pay Structure
    pay_grade VARCHAR(50),
    band_minimum DECIMAL(12,2),
    band_midpoint DECIMAL(12,2),
    band_maximum DECIMAL(12,2),
    current_compa_ratio DECIMAL(5,4),

    -- Performance (from Halogen/SuccessFactors)
    performance_score DECIMAL(3,1),
    performance_rating VARCHAR(50),

    -- Historical Rates (Year-specific columns)
    prior_year_rate DECIMAL(12,4),
    prior_year_increase_pct DECIMAL(5,2),
    current_year_rate DECIMAL(12,4),
    current_year_increase_pct DECIMAL(5,2),

    -- Bonus Eligibility
    gbp_eligible BOOLEAN DEFAULT FALSE,
    cap_bonus_eligible BOOLEAN DEFAULT FALSE,

    -- Prior Year Bonus Data
    prior_year_bonus DECIMAL(12,2),
    ytd_total DECIMAL(12,2),

    -- Flexible JSONB for additional year-specific data
    historical_data JSONB DEFAULT '{}',
    extra_attributes JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- RULES ENGINE
-- =============================================================================

-- Rule sets (named collections of rules)
CREATE TABLE IF NOT EXISTS comp_rule_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    version INT DEFAULT 1,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual rules
CREATE TABLE IF NOT EXISTS comp_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rule_set_id UUID NOT NULL REFERENCES comp_rule_sets(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    description TEXT,
    priority INT DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,

    -- Rule Type: merit, bonus, promotion, minimum_salary, cap, eligibility
    rule_type VARCHAR(50) NOT NULL,

    -- Conditions (JSONB with nested logic)
    conditions JSONB NOT NULL,

    -- Actions (what happens when conditions match)
    actions JSONB NOT NULL,

    -- Metadata
    effective_date DATE,
    expiry_date DATE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- SCENARIO MODELING
-- =============================================================================

-- Scenarios (each cycle can have multiple modeling scenarios)
CREATE TABLE IF NOT EXISTS comp_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Linked rule set
    rule_set_id UUID REFERENCES comp_rule_sets(id),

    -- Scenario configuration
    base_merit_percent DECIMAL(5,2),
    base_bonus_percent DECIMAL(5,2),
    budget_target_percent DECIMAL(5,2),

    -- Goal/guidance (can be natural language for LLM parsing)
    goal_description TEXT,

    -- Calculation status: draft, calculating, calculated, selected, archived
    status VARCHAR(50) DEFAULT 'draft',
    calculated_at TIMESTAMPTZ,

    -- Aggregated results (calculated)
    total_current_payroll DECIMAL(15,2),
    total_recommended_increase DECIMAL(15,2),
    overall_increase_percent DECIMAL(5,4),
    employees_affected INT,

    -- Selection
    is_selected BOOLEAN DEFAULT FALSE,
    selected_by UUID REFERENCES users(id),
    selected_at TIMESTAMPTZ,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-employee scenario results
CREATE TABLE IF NOT EXISTS comp_scenario_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scenario_id UUID NOT NULL REFERENCES comp_scenarios(id) ON DELETE CASCADE,
    employee_snapshot_id UUID NOT NULL REFERENCES comp_employee_snapshots(id) ON DELETE CASCADE,

    -- System recommendations (from rules engine)
    recommended_raise_percent DECIMAL(5,2),
    recommended_raise_amount DECIMAL(12,2),
    recommended_new_salary DECIMAL(12,2),
    recommended_new_hourly DECIMAL(12,4),
    recommended_bonus_percent DECIMAL(5,2),
    recommended_bonus_amount DECIMAL(12,2),

    -- Calculated values
    proposed_compa_ratio DECIMAL(5,4),
    total_increase_percent DECIMAL(5,2),
    total_increase_amount DECIMAL(12,2),

    -- Flags
    promotion_flag BOOLEAN DEFAULT FALSE,
    cap_bonus_flag BOOLEAN DEFAULT FALSE,
    needs_review_flag BOOLEAN DEFAULT FALSE,
    excluded_flag BOOLEAN DEFAULT FALSE,

    -- Rule tracking
    applied_rules JSONB DEFAULT '[]',
    rule_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- MANAGER WORKSHEET (Where managers input their decisions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS comp_worksheet_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,
    scenario_id UUID REFERENCES comp_scenarios(id),
    employee_snapshot_id UUID NOT NULL REFERENCES comp_employee_snapshots(id) ON DELETE CASCADE,

    -- System proposed values (copied from scenario_results when worksheet is created)
    system_raise_percent DECIMAL(5,2),
    system_raise_amount DECIMAL(12,2),
    system_new_salary DECIMAL(12,2),
    system_bonus_percent DECIMAL(5,2),
    system_bonus_amount DECIMAL(12,2),

    -- Manager input (editable)
    manager_raise_percent DECIMAL(5,2),
    manager_raise_amount DECIMAL(12,2),
    manager_new_salary DECIMAL(12,2),
    manager_bonus_percent DECIMAL(5,2),
    manager_bonus_amount DECIMAL(12,2),
    manager_promotion_flag BOOLEAN DEFAULT FALSE,
    manager_justification TEXT,
    manager_exception_flag BOOLEAN DEFAULT FALSE,

    -- Calculated deltas
    delta_raise_percent DECIMAL(5,2),
    delta_bonus_amount DECIMAL(12,2),

    -- Workflow status: pending, submitted, approved, rejected, flagged
    status VARCHAR(50) DEFAULT 'pending',

    -- Submitted by direct manager
    submitted_by UUID REFERENCES users(id),
    submitted_at TIMESTAMPTZ,

    -- Reviewed by (VP/Director level)
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- Final approval (C-level or Comp team)
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,

    -- Color coding (like Excel conditional formatting)
    highlight_color VARCHAR(20),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- COMMENTS & COLLABORATION
-- =============================================================================

CREATE TABLE IF NOT EXISTS comp_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Can be attached to various entities
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,

    author_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    mentions UUID[] DEFAULT '{}',

    -- Threading
    parent_id UUID REFERENCES comp_comments(id),

    -- Flagging
    is_question BOOLEAN DEFAULT FALSE,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- APPROVAL WORKFLOW
-- =============================================================================

CREATE TABLE IF NOT EXISTS comp_approval_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,

    -- Approver hierarchy
    approver_user_id UUID NOT NULL REFERENCES users(id),
    approver_role VARCHAR(50),
    approval_level INT NOT NULL,

    -- Scope (what they approve)
    scope_type VARCHAR(50),
    scope_department_id UUID,
    scope_business_unit VARCHAR(100),

    -- Status: pending, approved, rejected
    status VARCHAR(50) DEFAULT 'pending',
    approved_at TIMESTAMPTZ,
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- EXPORT & AUDIT
-- =============================================================================

CREATE TABLE IF NOT EXISTS comp_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id),

    export_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255),
    file_url TEXT,

    row_count INT,
    exported_by UUID REFERENCES users(id),
    exported_at TIMESTAMPTZ DEFAULT NOW(),

    -- Dayforce specific
    dayforce_batch_id VARCHAR(100),
    dayforce_status VARCHAR(50),

    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comp_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,

    user_id UUID REFERENCES users(id),
    old_values JSONB,
    new_values JSONB,

    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_comp_cycles_tenant_status ON comp_cycles(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_comp_cycles_fiscal_year ON comp_cycles(tenant_id, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_comp_dataset_versions_cycle ON comp_dataset_versions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_comp_employee_snapshots_dataset ON comp_employee_snapshots(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_comp_employee_snapshots_employee ON comp_employee_snapshots(tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_comp_rules_ruleset ON comp_rules(rule_set_id);
CREATE INDEX IF NOT EXISTS idx_comp_scenarios_cycle ON comp_scenarios(cycle_id);
CREATE INDEX IF NOT EXISTS idx_comp_scenario_results_scenario ON comp_scenario_results(scenario_id);
CREATE INDEX IF NOT EXISTS idx_comp_scenario_results_employee ON comp_scenario_results(employee_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_comp_worksheet_entries_cycle ON comp_worksheet_entries(cycle_id, status);
CREATE INDEX IF NOT EXISTS idx_comp_worksheet_entries_employee ON comp_worksheet_entries(employee_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_comp_comments_entity ON comp_comments(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_comp_approval_chains_cycle ON comp_approval_chains(cycle_id);
CREATE INDEX IF NOT EXISTS idx_comp_exports_cycle ON comp_exports(cycle_id);
CREATE INDEX IF NOT EXISTS idx_comp_audit_log_entity ON comp_audit_log(entity_type, entity_id);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE comp_cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_dataset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_employee_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_rule_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_scenario_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_worksheet_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_approval_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_audit_log ENABLE ROW LEVEL SECURITY;

-- Standard tenant isolation policies
CREATE POLICY comp_cycles_tenant_isolation ON comp_cycles
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_dataset_versions_tenant_isolation ON comp_dataset_versions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_employee_snapshots_tenant_isolation ON comp_employee_snapshots
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_rule_sets_tenant_isolation ON comp_rule_sets
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_rules_tenant_isolation ON comp_rules
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_scenarios_tenant_isolation ON comp_scenarios
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_scenario_results_tenant_isolation ON comp_scenario_results
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_worksheet_entries_tenant_isolation ON comp_worksheet_entries
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_comments_tenant_isolation ON comp_comments
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_approval_chains_tenant_isolation ON comp_approval_chains
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_exports_tenant_isolation ON comp_exports
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY comp_audit_log_tenant_isolation ON comp_audit_log
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

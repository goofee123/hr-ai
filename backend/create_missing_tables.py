#!/usr/bin/env python3
"""Create missing compensation tables via Supabase REST API."""

import httpx

SUPABASE_URL = "https://kzzrispvnnhcrifaeusk.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6enJpc3B2bm5oY3JpZmFldXNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE1ODM0NywiZXhwIjoyMDgwNzM0MzQ3fQ.8CAIBdKLHeFuzvDkKHppYCOau_rfftwQ_VzIuCKC1k4"

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Get existing tenant_id and cycle_id for testing
response = httpx.get(
    f"{SUPABASE_URL}/rest/v1/comp_cycles?select=id,tenant_id&limit=1",
    headers=headers,
    timeout=10.0
)
if response.status_code == 200 and response.json():
    cycle = response.json()[0]
    tenant_id = cycle["tenant_id"]
    cycle_id = cycle["id"]
    print(f"Found tenant_id: {tenant_id}")
    print(f"Found cycle_id: {cycle_id}")
else:
    print("No cycles found")
    tenant_id = None
    cycle_id = None

# The missing tables we need - let's try inserting into them to see if they get auto-created
# Actually, Supabase doesn't auto-create tables - we need to run the migration manually

# Let's output the SQL for the missing tables
missing_tables_sql = """
-- =============================================================================
-- MISSING COMPENSATION TABLES (copy to Supabase SQL Editor)
-- =============================================================================

-- Employee compensation snapshots
CREATE TABLE IF NOT EXISTS comp_employee_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES comp_dataset_versions(id) ON DELETE CASCADE,
    employee_id VARCHAR(50) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    business_unit VARCHAR(100),
    department VARCHAR(100),
    sub_department VARCHAR(100),
    manager_name VARCHAR(200),
    manager_employee_id VARCHAR(50),
    job_title VARCHAR(200),
    hire_date DATE,
    last_increase_date DATE,
    employment_type VARCHAR(50),
    schedule VARCHAR(50),
    weekly_hours DECIMAL(5,2) DEFAULT 40,
    location VARCHAR(100),
    country VARCHAR(50),
    current_hourly_rate DECIMAL(12,4),
    current_weekly DECIMAL(12,2),
    current_annual DECIMAL(12,2),
    pay_grade VARCHAR(50),
    band_minimum DECIMAL(12,2),
    band_midpoint DECIMAL(12,2),
    band_maximum DECIMAL(12,2),
    current_compa_ratio DECIMAL(5,4),
    performance_score DECIMAL(3,1),
    performance_rating VARCHAR(50),
    prior_year_rate DECIMAL(12,4),
    prior_year_increase_pct DECIMAL(5,2),
    current_year_rate DECIMAL(12,4),
    current_year_increase_pct DECIMAL(5,2),
    gbp_eligible BOOLEAN DEFAULT FALSE,
    cap_bonus_eligible BOOLEAN DEFAULT FALSE,
    prior_year_bonus DECIMAL(12,2),
    ytd_total DECIMAL(12,2),
    historical_data JSONB DEFAULT '{}',
    extra_attributes JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-employee scenario results
CREATE TABLE IF NOT EXISTS comp_scenario_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scenario_id UUID NOT NULL REFERENCES comp_scenarios(id) ON DELETE CASCADE,
    employee_snapshot_id UUID NOT NULL REFERENCES comp_employee_snapshots(id) ON DELETE CASCADE,
    recommended_raise_percent DECIMAL(5,2),
    recommended_raise_amount DECIMAL(12,2),
    recommended_new_salary DECIMAL(12,2),
    recommended_new_hourly DECIMAL(12,4),
    recommended_bonus_percent DECIMAL(5,2),
    recommended_bonus_amount DECIMAL(12,2),
    proposed_compa_ratio DECIMAL(5,4),
    total_increase_percent DECIMAL(5,2),
    total_increase_amount DECIMAL(12,2),
    promotion_flag BOOLEAN DEFAULT FALSE,
    cap_bonus_flag BOOLEAN DEFAULT FALSE,
    needs_review_flag BOOLEAN DEFAULT FALSE,
    excluded_flag BOOLEAN DEFAULT FALSE,
    applied_rules JSONB DEFAULT '[]',
    rule_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Manager worksheet
CREATE TABLE IF NOT EXISTS comp_worksheet_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,
    scenario_id UUID REFERENCES comp_scenarios(id),
    employee_snapshot_id UUID NOT NULL REFERENCES comp_employee_snapshots(id) ON DELETE CASCADE,
    system_raise_percent DECIMAL(5,2),
    system_raise_amount DECIMAL(12,2),
    system_new_salary DECIMAL(12,2),
    system_bonus_percent DECIMAL(5,2),
    system_bonus_amount DECIMAL(12,2),
    manager_raise_percent DECIMAL(5,2),
    manager_raise_amount DECIMAL(12,2),
    manager_new_salary DECIMAL(12,2),
    manager_bonus_percent DECIMAL(5,2),
    manager_bonus_amount DECIMAL(12,2),
    manager_promotion_flag BOOLEAN DEFAULT FALSE,
    manager_justification TEXT,
    manager_exception_flag BOOLEAN DEFAULT FALSE,
    delta_raise_percent DECIMAL(5,2),
    delta_bonus_amount DECIMAL(12,2),
    status VARCHAR(50) DEFAULT 'pending',
    submitted_by UUID REFERENCES users(id),
    submitted_at TIMESTAMPTZ,
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,
    highlight_color VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comments & Collaboration
CREATE TABLE IF NOT EXISTS comp_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    author_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    mentions UUID[] DEFAULT '{}',
    parent_id UUID REFERENCES comp_comments(id),
    is_question BOOLEAN DEFAULT FALSE,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Approval workflow
CREATE TABLE IF NOT EXISTS comp_approval_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES comp_cycles(id) ON DELETE CASCADE,
    approver_user_id UUID NOT NULL REFERENCES users(id),
    approver_role VARCHAR(50),
    approval_level INT NOT NULL,
    scope_type VARCHAR(50),
    scope_department_id UUID,
    scope_business_unit VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    approved_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Export tracking
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
    dayforce_batch_id VARCHAR(100),
    dayforce_status VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
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

-- Enable RLS
ALTER TABLE comp_employee_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_scenario_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_worksheet_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_approval_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_audit_log ENABLE ROW LEVEL SECURITY;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_comp_employee_snapshots_dataset ON comp_employee_snapshots(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_comp_employee_snapshots_employee ON comp_employee_snapshots(tenant_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_comp_scenario_results_scenario ON comp_scenario_results(scenario_id);
CREATE INDEX IF NOT EXISTS idx_comp_worksheet_entries_cycle ON comp_worksheet_entries(cycle_id, status);
CREATE INDEX IF NOT EXISTS idx_comp_worksheet_entries_employee ON comp_worksheet_entries(employee_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_comp_comments_entity ON comp_comments(entity_type, entity_id);
"""

print("\n" + "=" * 70)
print("MISSING TABLES SQL")
print("=" * 70)
print("\nCopy the following SQL to Supabase SQL Editor:")
print("-" * 70)
print(missing_tables_sql)
print("-" * 70)

# Also save to a file for easy copy
with open("missing_tables.sql", "w") as f:
    f.write(missing_tables_sql)

print("\nSQL also saved to: missing_tables.sql")
print("\nTo create the tables:")
print("1. Go to: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new")
print("2. Paste the SQL above")
print("3. Click 'Run'")

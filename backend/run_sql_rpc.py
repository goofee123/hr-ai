#!/usr/bin/env python3
"""Run SQL via Supabase RPC (pg_exec function if available)."""

import httpx
import json

SUPABASE_URL = "https://kzzrispvnnhcrifaeusk.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6enJpc3B2bm5oY3JpZmFldXNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE1ODM0NywiZXhwIjoyMDgwNzM0MzQ3fQ.8CAIBdKLHeFuzvDkKHppYCOau_rfftwQ_VzIuCKC1k4"

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Individual SQL statements to create tables one at a time
tables_sql = [
    # 1. comp_employee_snapshots
    """CREATE TABLE IF NOT EXISTS comp_employee_snapshots (
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
    )""",
    # Continue with more...
]

# Let's try using the pg_query or exec_sql RPC if available
print("Testing Supabase RPC endpoint...")

# Try calling a simple SQL function
test_response = httpx.post(
    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
    headers=headers,
    json={"query": "SELECT 1 as test"},
    timeout=30.0
)
print(f"exec_sql RPC: {test_response.status_code}")
if test_response.status_code != 200:
    print(f"Response: {test_response.text[:200]}")

# Alternative - try pg_query
test_response2 = httpx.post(
    f"{SUPABASE_URL}/rest/v1/rpc/pg_query",
    headers=headers,
    json={"query": "SELECT 1 as test"},
    timeout=30.0
)
print(f"pg_query RPC: {test_response2.status_code}")
if test_response2.status_code != 200:
    print(f"Response: {test_response2.text[:200]}")

print("\n" + "=" * 70)
print("NOTE: Supabase doesn't allow DDL via REST API by default.")
print("=" * 70)
print("\nYou need to run the migration manually via Supabase Dashboard.")
print("\nDashboard URL: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new")
print("\nAlternatively, use the Supabase CLI:")
print("  1. Install: npm install -g supabase")
print("  2. Link: supabase link --project-ref kzzrispvnnhcrifaeusk")
print("  3. Run: supabase db push")

#!/usr/bin/env python3
"""Check all compensation tables."""

import httpx

SUPABASE_URL = "https://kzzrispvnnhcrifaeusk.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6enJpc3B2bm5oY3JpZmFldXNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE1ODM0NywiZXhwIjoyMDgwNzM0MzQ3fQ.8CAIBdKLHeFuzvDkKHppYCOau_rfftwQ_VzIuCKC1k4"

tables = [
    "comp_cycles",
    "comp_dataset_versions",
    "comp_employee_snapshots",
    "comp_rule_sets",
    "comp_rules",
    "comp_scenarios",
    "comp_scenario_results",
    "comp_worksheet_entries",
    "comp_comments",
    "comp_approval_chains",
    "comp_exports",
    "comp_audit_log",
]

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}

print("Checking compensation tables...")
print("-" * 50)

for table in tables:
    try:
        response = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=count",
            headers=headers,
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            print(f"  {table}: EXISTS ({len(data)} rows)")
        else:
            print(f"  {table}: NOT FOUND ({response.status_code})")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")

print("-" * 50)

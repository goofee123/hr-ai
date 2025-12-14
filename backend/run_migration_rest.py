#!/usr/bin/env python3
"""Run database migrations using Supabase REST API."""

import httpx
import json

# Supabase configuration
SUPABASE_URL = "https://kzzrispvnnhcrifaeusk.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6enJpc3B2bm5oY3JpZmFldXNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE1ODM0NywiZXhwIjoyMDgwNzM0MzQ3fQ.8CAIBdKLHeFuzvDkKHppYCOau_rfftwQ_VzIuCKC1k4"

def run_migration():
    """Execute compensation module migration via Supabase REST API."""

    # The tables to create - we'll use the REST API to create them by inserting data
    # Supabase auto-creates tables if the policy allows (via service role)

    # However, Supabase REST API doesn't support DDL commands
    # We need to use the Supabase SQL Editor in the dashboard
    # OR use the Supabase Management API

    # Let's print out instructions for running the migration manually
    print("=" * 70)
    print("COMPENSATION MODULE DATABASE MIGRATION")
    print("=" * 70)
    print()
    print("The database tables need to be created via the Supabase Dashboard.")
    print()
    print("Steps to run the migration:")
    print()
    print("1. Go to Supabase Dashboard:")
    print(f"   {SUPABASE_URL.replace('https://', 'https://supabase.com/dashboard/project/').replace('.supabase.co', '')}")
    print()
    print("2. Navigate to: SQL Editor (left sidebar)")
    print()
    print("3. Copy the contents of this file:")
    print("   /home/goofe/hrai/backend/database/migrations/007_compensation_module.sql")
    print()
    print("4. Paste and run the SQL in the editor")
    print()
    print("-" * 70)
    print("ALTERNATIVE: Run via psql with direct connection")
    print("-" * 70)
    print()
    print("If you have psql installed and direct database access enabled:")
    print()
    print("psql 'postgresql://postgres:PASSWORD@db.kzzrispvnnhcrifaeusk.supabase.co:5432/postgres' \\")
    print("     -f /home/goofe/hrai/backend/database/migrations/007_compensation_module.sql")
    print()
    print("=" * 70)

    # Let's test if we can at least connect to the REST API
    print("\nTesting Supabase REST API connection...")

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }

    try:
        # Test connection by checking if tables exist
        response = httpx.get(
            f"{SUPABASE_URL}/rest/v1/comp_cycles?select=count",
            headers=headers,
            timeout=10.0
        )

        if response.status_code == 200:
            print("SUCCESS: comp_cycles table exists!")
            data = response.json()
            print(f"Current row count: {len(data)}")
        elif response.status_code == 404:
            print("INFO: comp_cycles table does NOT exist yet.")
            print("Please run the migration SQL in Supabase Dashboard.")
        else:
            print(f"Response: {response.status_code}")
            print(response.text[:500])

        # Check other tables
        for table in ["comp_rule_sets", "comp_scenarios", "comp_worksheet_entries"]:
            response = httpx.get(
                f"{SUPABASE_URL}/rest/v1/{table}?select=count",
                headers=headers,
                timeout=10.0
            )
            status = "EXISTS" if response.status_code == 200 else "NOT FOUND"
            print(f"  {table}: {status}")

    except Exception as e:
        print(f"Error connecting to Supabase: {e}")

if __name__ == "__main__":
    run_migration()

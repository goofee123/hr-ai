#!/usr/bin/env python3
"""
Run SQL migrations in Supabase.

This script reads SQL files from the migrations directory and executes them
using the Supabase Management API (requires access_token) or via the SQL Editor
API endpoint.

Usage:
    python run_migration.py <migration_file>

Note: For production use, you should run these migrations directly in the
Supabase Dashboard SQL Editor or use the Supabase CLI.
"""

import os
import sys
import httpx

# Supabase configuration from environment or hardcoded (for development only)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kzzrispvnnhcrifaeusk.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6enJpc3B2bm5oY3JpZmFldXNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE1ODM0NywiZXhwIjoyMDgwNzM0MzQ3fQ.8CAIBdKLHeFuzvDkKHppYCOau_rfftwQ_VzIuCKC1k4")


def run_sql(sql: str) -> dict:
    """Execute SQL via Supabase's RPC endpoint (for functions only)."""
    # Note: This only works for executing stored functions
    # For DDL statements, use the Supabase Dashboard or CLI
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        headers=headers,
        json={"query": sql},
        timeout=60,
    )

    return {"status": response.status_code, "body": response.text}


def main():
    if len(sys.argv) < 2:
        # Default to showing available migrations
        migrations_dir = os.path.dirname(os.path.abspath(__file__)) + "/migrations"
        print(f"Available migrations in {migrations_dir}:")
        for f in sorted(os.listdir(migrations_dir)):
            if f.endswith(".sql"):
                print(f"  - {f}")
        print("\nTo run a migration, go to the Supabase Dashboard:")
        print("  1. Open https://supabase.com/dashboard")
        print("  2. Select your project: kzzrispvnnhcrifaeusk")
        print("  3. Go to SQL Editor")
        print("  4. Paste the contents of the migration file")
        print("  5. Click 'Run'")
        return

    migration_file = sys.argv[1]

    # Check if file exists
    if not os.path.exists(migration_file):
        # Try relative to migrations directory
        migrations_dir = os.path.dirname(os.path.abspath(__file__)) + "/migrations"
        migration_file = os.path.join(migrations_dir, migration_file)

    if not os.path.exists(migration_file):
        print(f"Error: Migration file not found: {migration_file}")
        sys.exit(1)

    # Read the SQL file
    with open(migration_file, "r") as f:
        sql = f.read()

    print(f"Migration file: {migration_file}")
    print(f"SQL length: {len(sql)} characters")
    print("\n" + "="*60)
    print("IMPORTANT: Run this migration in Supabase Dashboard")
    print("="*60)
    print("\n1. Open: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql")
    print("2. Paste the following SQL:")
    print("\n" + "-"*60)
    print(sql[:2000] + ("..." if len(sql) > 2000 else ""))
    print("-"*60)
    print(f"\n(Full migration file: {migration_file})")


if __name__ == "__main__":
    main()

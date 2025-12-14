#!/usr/bin/env python3
"""Run database migration using direct PostgreSQL connection with SSL."""

import ssl
import socket

# Try with psycopg2 using explicit SSL
try:
    import psycopg2
    from psycopg2 import sql

    # Direct database connection (port 5432, not pooler 6543)
    # With IPv4 explicit
    host = "db.kzzrispvnnhcrifaeusk.supabase.co"

    # Resolve to IPv4 explicitly
    try:
        ipv4_addr = socket.gethostbyname(host)
        print(f"Resolved {host} to {ipv4_addr}")
    except Exception as e:
        print(f"DNS resolution failed: {e}")
        ipv4_addr = host

    DATABASE_URL = f"postgresql://postgres:G00gl_9027!@{ipv4_addr}:5432/postgres?sslmode=require"

    print(f"Connecting to: {DATABASE_URL[:50]}...")

    conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
    conn.autocommit = True
    cur = conn.cursor()

    print("Connected! Running migration...")

    # Read and execute migration
    with open("database/migrations/007_compensation_module.sql", "r") as f:
        migration_sql = f.read()

    # Split by statement (simplified)
    statements = migration_sql.split(";")
    success = 0
    errors = 0

    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            cur.execute(stmt + ";")
            success += 1
        except Exception as e:
            err_msg = str(e).lower()
            if "already exists" not in err_msg:
                print(f"Error: {str(e)[:100]}")
                errors += 1
            else:
                success += 1  # "already exists" is OK

    print(f"\nMigration complete: {success} succeeded, {errors} errors")

    cur.close()
    conn.close()

except Exception as e:
    print(f"Connection failed: {e}")
    print("\nThe database may not be reachable from this environment.")
    print("Please run the migration manually via Supabase Dashboard:")
    print("  1. Go to: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new")
    print("  2. Paste contents of: database/migrations/007_compensation_module.sql")
    print("  3. Click 'Run'")

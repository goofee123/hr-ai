#!/usr/bin/env python3
"""Run database migrations for Compensation module."""

import os
import psycopg2

# Use direct connection (not pooler) for migrations
# Supabase direct connection format: db.<project-ref>.supabase.co
DATABASE_URL = "postgresql://postgres:G00gl_9027!@db.kzzrispvnnhcrifaeusk.supabase.co:5432/postgres"

def run_migration():
    """Execute the compensation module migration."""
    # Read the migration file
    migration_file = "database/migrations/007_compensation_module.sql"

    with open(migration_file, "r") as f:
        sql = f.read()

    print(f"Migration file loaded: {migration_file}")
    print(f"Size: {len(sql)} bytes")

    # Connect to database
    print("\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Execute the entire SQL file
    print("Running migration...")
    try:
        cur.execute(sql)
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error: {e}")

        # Try executing statement by statement
        print("\nTrying statement by statement...")

        # Remove comments and split properly
        lines = sql.split('\n')
        clean_sql = []
        in_comment = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('--'):
                continue
            if '/*' in line:
                in_comment = True
            if '*/' in line:
                in_comment = False
                continue
            if not in_comment:
                clean_sql.append(line)

        full_sql = '\n'.join(clean_sql)

        # Split by semicolons, being careful about function bodies
        statements = []
        current = []
        paren_depth = 0

        for char in full_sql:
            current.append(char)
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ';' and paren_depth == 0:
                stmt = ''.join(current).strip()
                if stmt and stmt != ';':
                    statements.append(stmt)
                current = []

        success = 0
        errors = 0

        for i, stmt in enumerate(statements):
            stmt = stmt.strip()
            if not stmt or stmt == ';':
                continue
            try:
                cur.execute(stmt)
                success += 1
            except Exception as e2:
                error_msg = str(e2)
                if "already exists" not in error_msg.lower():
                    print(f"  Statement {i+1} error: {error_msg[:80]}")
                    errors += 1
                else:
                    success += 1  # Count as success if already exists

        print(f"\nResults: {success} succeeded, {errors} errors")

    cur.close()
    conn.close()
    print("Connection closed.")

if __name__ == "__main__":
    run_migration()

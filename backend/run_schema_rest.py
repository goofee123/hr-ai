"""Run the database schema via Supabase REST API."""
import httpx

SUPABASE_URL = "https://kzzrispvnnhcrifaeusk.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt6enJpc3B2bm5oY3JpZmFldXNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTE1ODM0NywiZXhwIjoyMDgwNzM0MzQ3fQ.8CAIBdKLHeFuzvDkKHppYCOau_rfftwQ_VzIuCKC1k4"

# Read the schema file
with open("/home/goofe/hrai/database/schema.sql", "r") as f:
    schema_sql = f.read()

# Split into statements (simple split - may need refinement for complex SQL)
# For now, let's try executing the whole thing via the SQL endpoint
headers = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

print("Executing SQL via Supabase REST API...")

# Use the /rest/v1/rpc endpoint to run raw SQL
# Actually, Supabase doesn't have a direct SQL execution endpoint via REST
# We need to use the management API or the SQL editor

# Let's try the pg_graphql or direct query approach
# The better approach is to use supabase-py with service role

print("Installing supabase-py...")
import subprocess
subprocess.run(["pip", "install", "supabase"], capture_output=True)

from supabase import create_client, Client

print("Connecting to Supabase...")
supabase: Client = create_client(SUPABASE_URL, SERVICE_KEY)

# Unfortunately, supabase-py doesn't support raw SQL execution either
# The only way to run DDL is through:
# 1. psql (network blocked)
# 2. Supabase Dashboard SQL Editor (manual)
# 3. Supabase CLI (not installed)
# 4. Management API (limited)

print("\n" + "="*60)
print("NETWORK LIMITATION DETECTED")
print("="*60)
print("""
The direct PostgreSQL connection is blocked from this environment.
This is likely due to WSL network restrictions or firewall rules.

OPTIONS TO RUN THE SCHEMA:

1. SUPABASE DASHBOARD (Easiest):
   - Go to: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql
   - Copy/paste the schema from: /home/goofe/hrai/database/schema.sql
   - Click "Run"

2. SUPABASE CLI (if you install it):
   npx supabase db push

3. FROM YOUR LOCAL MACHINE (not WSL):
   If you have psql installed locally, run:
   PGPASSWORD='G00gl_9027!' psql "postgresql://postgres.kzzrispvnnhcrifaeusk@db.kzzrispvnnhcrifaeusk.supabase.co:5432/postgres" -f schema.sql

The schema file is ready at:
/home/goofe/hrai/database/schema.sql
""")

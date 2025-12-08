"""Run the database schema against Supabase."""
import psycopg2

# Try direct connection (port 5432) instead of pooler (6543)
# Format: postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
conn_string = "postgresql://postgres.kzzrispvnnhcrifaeusk:G00gl_9027!@db.kzzrispvnnhcrifaeusk.supabase.co:5432/postgres"

# Read the schema file
with open("/home/goofe/hrai/database/schema.sql", "r") as f:
    schema_sql = f.read()

print("Connecting to Supabase PostgreSQL (direct connection)...")
conn = psycopg2.connect(conn_string)
conn.autocommit = True
cur = conn.cursor()

print("Running schema...")
try:
    cur.execute(schema_sql)
    print("Schema executed successfully!")
except psycopg2.Error as e:
    print(f"Error: {e}")
finally:
    cur.close()
    conn.close()
    print("Connection closed.")

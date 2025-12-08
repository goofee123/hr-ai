# PowerShell script to run the HRM-Core database schema on Supabase
# Run this from Windows (not WSL) where PostgreSQL connectivity works

$ErrorActionPreference = "Stop"

# Supabase PostgreSQL connection details
$PGHOST = "db.kzzrispvnnhcrifaeusk.supabase.co"
$PGPORT = "5432"
$PGDATABASE = "postgres"
$PGUSER = "postgres.kzzrispvnnhcrifaeusk"
$PGPASSWORD = "G00gl_9027!"

# Set environment variables
$env:PGPASSWORD = $PGPASSWORD

# Path to schema file (adjust if needed)
$SchemaFile = Join-Path $PSScriptRoot "schema.sql"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "HRM-Core Database Schema Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Supabase Project: kzzrispvnnhcrifaeusk"
Write-Host "Database Host: $PGHOST"
Write-Host "Schema File: $SchemaFile"
Write-Host ""

# Check if psql is available
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue

if ($null -eq $psqlPath) {
    Write-Host "ERROR: psql is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install PostgreSQL client tools:" -ForegroundColor Yellow
    Write-Host "  Option 1: Install full PostgreSQL from https://www.postgresql.org/download/windows/"
    Write-Host "  Option 2: Install pgAdmin 4 (includes psql)"
    Write-Host "  Option 3: Use Chocolatey: choco install postgresql"
    Write-Host ""
    Write-Host "After installing, restart your terminal and run this script again."
    exit 1
}

Write-Host "Found psql at: $($psqlPath.Source)" -ForegroundColor Green
Write-Host ""

# Test connection first
Write-Host "Testing database connection..." -ForegroundColor Yellow
$testResult = psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "SELECT 1;" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to connect to database" -ForegroundColor Red
    Write-Host $testResult
    exit 1
}

Write-Host "Connection successful!" -ForegroundColor Green
Write-Host ""

# Run the schema
Write-Host "Running schema..." -ForegroundColor Yellow
Write-Host "This may take a moment..."
Write-Host ""

psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f $SchemaFile 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Schema executed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. cd to /home/goofe/hrai/backend (in WSL)"
    Write-Host "  2. source venv/bin/activate"
    Write-Host "  3. uvicorn app.main:app --reload"
    Write-Host ""
    Write-Host "  4. cd to /home/goofe/hrai/frontend (in WSL)"
    Write-Host "  5. npm run dev"
} else {
    Write-Host ""
    Write-Host "Schema execution failed. Check the errors above." -ForegroundColor Red
    exit 1
}

-- =============================================================================
-- COMPENSATION MODULE - FIX comp_rules TABLE
-- Run this in Supabase Dashboard: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new
-- =============================================================================

-- Add missing columns to comp_rules table
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS priority INT DEFAULT 100;
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS rule_type VARCHAR(50);
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS conditions JSONB DEFAULT '{}';
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS actions JSONB DEFAULT '{}';
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS effective_date DATE;
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS expiry_date DATE;
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE comp_rules ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Enable RLS on comp_rules if not already enabled
ALTER TABLE comp_rules ENABLE ROW LEVEL SECURITY;

-- Create RLS policy for comp_rules (drop first if exists)
DO $$
BEGIN
    DROP POLICY IF EXISTS comp_rules_tenant_isolation ON comp_rules;
    CREATE POLICY comp_rules_tenant_isolation ON comp_rules
        FOR ALL USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'RLS policy may already exist or tenant setting not available: %', SQLERRM;
END
$$;

-- Create index on rule_set_id if not exists
CREATE INDEX IF NOT EXISTS idx_comp_rules_rule_set ON comp_rules(rule_set_id);

-- Done!
SELECT 'comp_rules table fix complete!' as status;

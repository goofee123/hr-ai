-- =============================================================================
-- COMPENSATION MODULE - FIX comp_scenarios TABLE
-- Run this in Supabase Dashboard: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new
-- =============================================================================

-- The comp_scenarios table has wrong schema. It has dataset_version_id instead of cycle_id.
-- We need to add cycle_id column and make dataset_version_id nullable.

-- Add cycle_id column (required for scenario-cycle relationship)
ALTER TABLE comp_scenarios ADD COLUMN IF NOT EXISTS cycle_id UUID REFERENCES comp_cycles(id) ON DELETE CASCADE;

-- Add created_by column
ALTER TABLE comp_scenarios ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);

-- Make dataset_version_id nullable (scenarios don't need to be tied to dataset version initially)
ALTER TABLE comp_scenarios ALTER COLUMN dataset_version_id DROP NOT NULL;

-- Create index on cycle_id for performance
CREATE INDEX IF NOT EXISTS idx_comp_scenarios_cycle ON comp_scenarios(cycle_id);

-- =============================================================================
-- ALSO FIX comp_rules TABLE (if 008 wasn't run)
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
SELECT 'comp_scenarios and comp_rules tables fixed!' as status;

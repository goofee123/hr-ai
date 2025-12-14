-- =============================================================================
-- COMPENSATION MODULE - CLEAN UP LEGACY comp_rules COLUMNS
-- Run this in Supabase Dashboard: https://supabase.com/dashboard/project/kzzrispvnnhcrifaeusk/sql/new
-- =============================================================================

-- The comp_rules table has legacy columns from the original schema:
-- - condition_expression (TEXT NOT NULL)
-- - action (comp_rule_action enum NOT NULL)
--
-- Since we now use JSONB columns 'conditions' and 'actions',
-- we should drop these legacy columns entirely.

-- First, drop the NOT NULL constraints (in case dropping column fails)
ALTER TABLE comp_rules ALTER COLUMN condition_expression DROP NOT NULL;

-- For enum column, we need to either:
-- 1. Drop the column entirely, OR
-- 2. Convert it to TEXT and make it nullable

-- Option 1: Drop the legacy columns (preferred - clean approach)
ALTER TABLE comp_rules DROP COLUMN IF EXISTS condition_expression;
ALTER TABLE comp_rules DROP COLUMN IF EXISTS action;

-- Drop the enum type if no longer needed
DROP TYPE IF EXISTS comp_rule_action;

-- Done!
SELECT 'comp_rules legacy columns cleaned up!' as status;

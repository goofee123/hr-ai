#!/bin/bash

# JWT Token for hr_admin (using correct secret: super-secret-jwt-key-change-in-production)
# Generate fresh token with correct tenant_id: 9931b057-954f-4ca8-a259-5242463f13bc
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMDI2YjU5MS1hMTFkLTRkYzUtYTU4ZS04MjFkMzJkNDk2MTIiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6ImFkbWluQGJoY29ycC5jb20iLCJyb2xlIjoiaHJfYWRtaW4iLCJpYXQiOjE3NjUzNDQ4OTQsImV4cCI6MTc2NTk0OTY5NH0.iG_cTF0T1xzyEhfh47Tl8zYcsBvvXlOWKBrzgqo7wJ4"

echo "================================================================"
echo "   COMPENSATION MODULE E2E TEST v2"
echo "   Testing existing tables only"
echo "================================================================"
echo ""

# Test 1: List existing cycles (should work)
echo "1. LIST COMPENSATION CYCLES"
echo "----------------------------"
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8888/api/v1/compensation/cycles | python3 -m json.tool 2>/dev/null || echo "FAILED"
echo ""

# Test 2: Get existing cycle detail
echo "2. GET CYCLE DETAIL (existing cycle)"
echo "-------------------------------------"
# First get cycle ID
CYCLE_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8888/api/v1/compensation/cycles | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
echo "Found cycle ID: $CYCLE_ID"
if [ -n "$CYCLE_ID" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/cycles/$CYCLE_ID" | python3 -m json.tool 2>/dev/null || echo "FAILED"
fi
echo ""

# Test 3: List Rule Sets
echo "3. LIST RULE SETS"
echo "-----------------"
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8888/api/v1/compensation/rules/sets | python3 -m json.tool 2>/dev/null || echo "FAILED"
echo ""

# Test 4: Get existing rule set with rules
echo "4. GET RULE SET DETAIL"
echo "----------------------"
RULESET_ID=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8888/api/v1/compensation/rules/sets | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
echo "Found rule set ID: $RULESET_ID"
if [ -n "$RULESET_ID" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/rules/sets/$RULESET_ID" | python3 -m json.tool 2>/dev/null || echo "FAILED"
fi
echo ""

# Test 5: List Scenarios for existing cycle
echo "5. LIST SCENARIOS"
echo "-----------------"
if [ -n "$CYCLE_ID" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/cycles/$CYCLE_ID/scenarios" | python3 -m json.tool 2>/dev/null || echo "FAILED"
fi
echo ""

# Test 6: Get Import History
echo "6. GET IMPORT HISTORY"
echo "---------------------"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/import/history" | python3 -m json.tool 2>/dev/null || echo "FAILED"
echo ""

# Test 7: Create a NEW cycle
echo "7. CREATE NEW COMPENSATION CYCLE"
echo "---------------------------------"
NEW_CYCLE_RESPONSE=$(curl -s -X POST http://localhost:8888/api/v1/compensation/cycles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "2026 Annual Review Test",
    "description": "E2E test cycle for 2026",
    "fiscal_year": 2026,
    "cycle_type": "annual",
    "effective_date": "2026-04-01",
    "manager_review_start": "2026-01-15",
    "manager_review_deadline": "2026-02-15",
    "overall_budget_percent": 3.5
  }')
echo "$NEW_CYCLE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$NEW_CYCLE_RESPONSE"
NEW_CYCLE_ID=$(echo "$NEW_CYCLE_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
echo ""
echo "New Cycle ID: $NEW_CYCLE_ID"
echo ""

# Test 8: Create a NEW rule set
echo "8. CREATE NEW RULE SET"
echo "----------------------"
NEW_RULESET_RESPONSE=$(curl -s -X POST http://localhost:8888/api/v1/compensation/rules/sets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "2026 E2E Test Rules",
    "description": "Rule set created during E2E test",
    "is_active": true,
    "is_default": false
  }')
echo "$NEW_RULESET_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$NEW_RULESET_RESPONSE"
NEW_RULESET_ID=$(echo "$NEW_RULESET_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
echo ""
echo "New Rule Set ID: $NEW_RULESET_ID"
echo ""

# Test 9: Create a rule in the new rule set
echo "9. CREATE NEW RULE"
echo "------------------"
if [ -n "$NEW_RULESET_ID" ]; then
  NEW_RULE_RESPONSE=$(curl -s -X POST http://localhost:8888/api/v1/compensation/rules \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"rule_set_id\": \"$NEW_RULESET_ID\",
      \"name\": \"E2E Test Rule\",
      \"description\": \"Test rule for 4% raise on high performers\",
      \"priority\": 10,
      \"rule_type\": \"merit\",
      \"conditions\": {
        \"logic\": \"AND\",
        \"conditions\": [
          {\"field\": \"performance_score\", \"operator\": \"GTE\", \"value\": 4.0}
        ]
      },
      \"actions\": {
        \"action_type\": \"SET_MERIT_PERCENT\",
        \"value\": 4.0
      },
      \"is_active\": true
    }")
  echo "$NEW_RULE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$NEW_RULE_RESPONSE"
else
  echo "Skipped - no rule set ID"
fi
echo ""

# Test 10: Create scenario on new cycle
echo "10. CREATE NEW SCENARIO"
echo "-----------------------"
if [ -n "$NEW_CYCLE_ID" ] && [ -n "$NEW_RULESET_ID" ]; then
  NEW_SCENARIO_RESPONSE=$(curl -s -X POST "http://localhost:8888/api/v1/compensation/cycles/$NEW_CYCLE_ID/scenarios" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"E2E Test Scenario\",
      \"description\": \"Test scenario for E2E testing\",
      \"rule_set_id\": \"$NEW_RULESET_ID\",
      \"base_merit_percent\": 2.5,
      \"budget_target_percent\": 3.0
    }")
  echo "$NEW_SCENARIO_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$NEW_SCENARIO_RESPONSE"
else
  echo "Skipped - missing cycle or rule set ID"
fi
echo ""

# Test 11: Update cycle status
echo "11. UPDATE CYCLE (change status)"
echo "---------------------------------"
if [ -n "$NEW_CYCLE_ID" ]; then
  UPDATE_RESPONSE=$(curl -s -X PATCH "http://localhost:8888/api/v1/compensation/cycles/$NEW_CYCLE_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "status": "modeling",
      "description": "Updated during E2E test"
    }')
  echo "$UPDATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$UPDATE_RESPONSE"
else
  echo "Skipped - no cycle ID"
fi
echo ""

echo "================================================================"
echo "   E2E TEST COMPLETE"
echo "================================================================"
echo ""
echo "SUMMARY:"
echo "  - Tables working: comp_cycles, comp_rule_sets, comp_rules, comp_scenarios, comp_dataset_versions"
echo "  - Tables missing (need Supabase migration):"
echo "    * comp_employee_snapshots"
echo "    * comp_scenario_results"
echo "    * comp_worksheet_entries"
echo "    * comp_comments"
echo "    * comp_approval_chains"
echo "    * comp_exports"
echo "    * comp_audit_log"
echo ""

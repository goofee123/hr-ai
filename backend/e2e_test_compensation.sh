#!/bin/bash

# JWT Token for hr_admin
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMDI2YjU5MS1hMTFkLTRkYzUtYTU4ZS04MjFkMzJkNDk2MTIiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzMWYzYmMiLCJlbWFpbCI6ImFkbWluQGJoY29ycC5jb20iLCJyb2xlIjoiaHJfYWRtaW4iLCJpYXQiOjE3NjUzMzcyMjgsImV4cCI6MTc2NTk0MjAyOH0.3oLrjAm1uypliISRlpAI56eqCbXbURtwd2AknwFe1TM"

echo "================================================================"
echo "   COMPENSATION MODULE E2E TEST"
echo "================================================================"
echo ""

# Test 1: Create Compensation Cycle
echo "1. CREATE COMPENSATION CYCLE"
echo "----------------------------"
CYCLE_RESPONSE=$(curl -s -X POST http://localhost:8888/api/v1/compensation/cycles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "2025 Annual Review",
    "description": "Annual compensation review for fiscal year 2025",
    "fiscal_year": 2025,
    "cycle_type": "annual",
    "effective_date": "2025-04-01",
    "manager_review_start": "2025-01-15",
    "manager_review_deadline": "2025-02-15",
    "overall_budget_percent": 3.5
  }')
echo "$CYCLE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CYCLE_RESPONSE"
CYCLE_ID=$(echo "$CYCLE_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
echo ""
echo "Cycle ID: $CYCLE_ID"
echo ""

# Test 2: List Cycles
echo "2. LIST COMPENSATION CYCLES"
echo "----------------------------"
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8888/api/v1/compensation/cycles | python3 -m json.tool 2>/dev/null
echo ""

# Test 3: Create Rule Set
echo "3. CREATE RULE SET"
echo "------------------"
RULESET_RESPONSE=$(curl -s -X POST http://localhost:8888/api/v1/compensation/rules/sets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "2025 Merit Rules",
    "description": "Standard merit increase rules for 2025",
    "is_active": true,
    "is_default": true
  }')
echo "$RULESET_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RULESET_RESPONSE"
RULESET_ID=$(echo "$RULESET_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
echo ""
echo "Rule Set ID: $RULESET_ID"
echo ""

# Test 4: Create a Rule
echo "4. CREATE RULE (High Performer Merit)"
echo "--------------------------------------"
if [ -n "$RULESET_ID" ]; then
  RULE_RESPONSE=$(curl -s -X POST http://localhost:8888/api/v1/compensation/rules \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"rule_set_id\": \"$RULESET_ID\",
      \"name\": \"High Performer Merit\",
      \"description\": \"4% raise for employees with performance score >= 4.0\",
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
        \"value\": 4.5
      },
      \"is_active\": true
    }")
  echo "$RULE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RULE_RESPONSE"
else
  echo "Skipped - no rule set ID"
fi
echo ""

# Test 5: List Rule Sets
echo "5. LIST RULE SETS"
echo "-----------------"
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8888/api/v1/compensation/rules/sets | python3 -m json.tool 2>/dev/null
echo ""

# Test 6: Create Scenario
echo "6. CREATE SCENARIO"
echo "------------------"
if [ -n "$CYCLE_ID" ]; then
  SCENARIO_RESPONSE=$(curl -s -X POST "http://localhost:8888/api/v1/compensation/cycles/$CYCLE_ID/scenarios" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"Conservative 3% Budget\",
      \"description\": \"Conservative scenario targeting 3% overall increase\",
      \"rule_set_id\": \"$RULESET_ID\",
      \"base_merit_percent\": 2.5,
      \"budget_target_percent\": 3.0
    }")
  echo "$SCENARIO_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SCENARIO_RESPONSE"
  SCENARIO_ID=$(echo "$SCENARIO_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  echo ""
  echo "Scenario ID: $SCENARIO_ID"
else
  echo "Skipped - no cycle ID"
fi
echo ""

# Test 7: List Scenarios for Cycle
echo "7. LIST SCENARIOS"
echo "-----------------"
if [ -n "$CYCLE_ID" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/cycles/$CYCLE_ID/scenarios" | python3 -m json.tool 2>/dev/null
else
  echo "Skipped - no cycle ID"
fi
echo ""

# Test 8: Get Worksheet (should be empty without employee data)
echo "8. GET WORKSHEET"
echo "----------------"
if [ -n "$CYCLE_ID" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/worksheets/$CYCLE_ID" | python3 -m json.tool 2>/dev/null
else
  echo "Skipped - no cycle ID"
fi
echo ""

# Test 9: Get Import History
echo "9. GET IMPORT HISTORY"
echo "---------------------"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/import/history" | python3 -m json.tool 2>/dev/null
echo ""

# Test 10: Get Cycle Detail
echo "10. GET CYCLE DETAIL"
echo "--------------------"
if [ -n "$CYCLE_ID" ]; then
  curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8888/api/v1/compensation/cycles/$CYCLE_ID" | python3 -m json.tool 2>/dev/null
else
  echo "Skipped - no cycle ID"
fi
echo ""

echo "================================================================"
echo "   E2E TEST COMPLETE"
echo "================================================================"

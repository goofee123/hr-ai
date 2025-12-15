# HRM-Core Recruiting Module: End-to-End Testing Plan

## Overview

This document provides a comprehensive E2E testing plan for the Recruiting module. It includes:
1. Sample test data (jobs and candidates)
2. Step-by-step portal testing sequences
3. Expected outcomes at each step
4. API verification commands

---

## Prerequisites

### 1. Backend Running
```bash
cd /home/goofe/hrai/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

### 2. Frontend Running
```bash
cd /home/goofe/hrai/frontend
npm run dev -- -p 3002
```

### 3. Test Token (Valid for 7 days)
```bash
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMDI2YjU5MS1hMTFkLTRkYzUtYTU4ZS04MjFkMzJkNDk2MTIiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6ImFkbWluQGJoY29ycC5jb20iLCJyb2xlIjoiaHJfYWRtaW4iLCJpYXQiOjE3NjU3NTgwODMsImV4cCI6MTc2NjM2Mjg4M30.qJko0-PLn0bKaTq1WulNGDsY2AyYCIE6HwVLpsY7g7w"
```

---

## Part 1: Sample Test Data

### Job Requisitions (Based on BH Dayforce Portal)

| # | Title | Department | Location | Type | Salary Range |
|---|-------|------------|----------|------|--------------|
| 1 | Senior Software Engineer | Engineering | Boston, MA | Full-time | $120,000 - $160,000 |
| 2 | HR Coordinator | Human Resources | Remote | Full-time | $55,000 - $70,000 |
| 3 | Financial Analyst | Finance | New York, NY | Full-time | $75,000 - $95,000 |
| 4 | Marketing Manager | Marketing | Chicago, IL | Full-time | $85,000 - $110,000 |
| 5 | Customer Success Rep | Customer Success | Remote | Full-time | $50,000 - $65,000 |
| 6 | Data Scientist | Engineering | Boston, MA | Full-time | $130,000 - $170,000 |
| 7 | Recruiter | Human Resources | Remote | Full-time | $60,000 - $80,000 |
| 8 | Product Manager | Product | San Francisco, CA | Full-time | $140,000 - $180,000 |
| 9 | Operations Analyst | Operations | Denver, CO | Full-time | $65,000 - $85,000 |
| 10 | Sales Development Rep | Sales | Austin, TX | Full-time | $45,000 - $60,000 + Commission |

### Sample Candidates for Testing

| # | Name | Email | Current Title | Experience | Skills |
|---|------|-------|---------------|------------|--------|
| 1 | John Smith | john.smith@email.com | Software Engineer | 5 years | Python, React, AWS |
| 2 | Sarah Johnson | sarah.j@email.com | HR Specialist | 3 years | HRIS, Recruiting, Compliance |
| 3 | Michael Chen | m.chen@email.com | Senior Developer | 8 years | Java, Python, ML, Kubernetes |
| 4 | Emily Davis | emily.davis@email.com | Marketing Coordinator | 2 years | Content, SEO, Analytics |
| 5 | Robert Wilson | r.wilson@email.com | Financial Analyst | 4 years | Excel, SQL, Financial Modeling |
| 6 | Jennifer Lee | jen.lee@email.com | Data Analyst | 3 years | Python, SQL, Tableau |
| 7 | David Brown | d.brown@email.com | Software Engineer | 5 years | Python, React, AWS | (Duplicate of John)
| 8 | Amanda Martinez | a.martinez@email.com | Product Analyst | 4 years | Jira, SQL, User Research |

---

## Part 2: Portal Testing Sequence

### Phase 1: Job Management (15 minutes)

#### Step 1.1: Create Job Requisitions via Portal
1. Navigate to: `http://localhost:3002/recruiting/jobs`
2. Click "New Job" or "Create Requisition"
3. Fill in the form with Job #1 data:
   - Title: Senior Software Engineer
   - Department: Engineering
   - Location: Boston, MA
   - Employment Type: Full-time
   - Salary Min: 120000
   - Salary Max: 160000
   - Description: "We are seeking a Senior Software Engineer to join our growing engineering team..."
   - Required Skills: Python, React, AWS
4. Click "Save" or "Create"
5. **Expected Result**: Job appears in the jobs list with status "Draft"

#### Step 1.2: Verify Job Creation via API
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/jobs | jq '.'
```
**Expected**: Returns list including the new job

#### Step 1.3: Open Job for Applications
1. Click on the created job to view details
2. Change status from "Draft" to "Open"
3. **Expected Result**: Status indicator changes, job is now accepting applications

#### Step 1.4: Repeat for 3-4 More Jobs
Create jobs #2, #3, #4 from the sample data above.

---

### Phase 2: Candidate Creation & Resume Upload (20 minutes)

#### Step 2.1: Add Candidate via Portal
1. Navigate to: `http://localhost:3002/recruiting/candidates`
2. Click "Add Candidate" or "New Candidate"
3. Fill in Candidate #1 data:
   - First Name: John
   - Last Name: Smith
   - Email: john.smith@email.com
   - Phone: 555-0101
   - Source: Direct Apply
4. Click "Save"
5. **Expected Result**: Candidate profile created

#### Step 2.2: Upload Resume
1. On the candidate profile page, find "Documents" or "Resumes" section
2. Click "Upload Resume"
3. Select a test PDF resume file
4. **Expected Result**:
   - Resume appears in documents list
   - LLM extraction queued (if enabled)
   - Parsed data populates candidate fields

#### Step 2.3: Verify Candidate via API
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/candidates | jq '.'
```

#### Step 2.4: View Observations (Extracted Data)
1. On candidate profile, look for "Observations" or "Extracted Data" tab
2. **Expected Result**: Shows extracted skills, experience, education with confidence scores

```bash
# API verification
CANDIDATE_ID="<uuid-from-previous-step>"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/observations/candidates/$CANDIDATE_ID/observations | jq '.'
```

#### Step 2.5: Add Multiple Candidates
Repeat steps 2.1-2.4 for candidates #2, #3, #4, #5, #6.

**Important**: Also add candidate #7 (David Brown) who is a duplicate of John Smith (same skills, similar background).

---

### Phase 3: Application Flow & Pipeline (15 minutes)

#### Step 3.1: Apply Candidate to Job
1. From candidate profile, click "Apply to Job" or "Add Application"
2. Select "Senior Software Engineer" job
3. **Expected Result**: Application created, candidate appears in job pipeline

Alternative: From job detail page, click "Add Candidate" and select existing candidate.

#### Step 3.2: Verify Pipeline View
1. Navigate to: `http://localhost:3002/recruiting/jobs/<job-id>`
2. **Expected Result**: Kanban board shows candidate in "Applied" stage

#### Step 3.3: Move Candidate Through Pipeline
1. Drag candidate card from "Applied" to "Phone Screen"
2. **Expected Result**:
   - Stage updates immediately
   - Activity event logged

```bash
# Verify activity logged
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/observations/candidates/$CANDIDATE_ID/activity | jq '.'
```

#### Step 3.4: Add Multiple Applications
Apply different candidates to different jobs to populate the pipeline.

---

### Phase 4: AI Matching & Recommendations (10 minutes)

#### Step 4.1: View Matching Candidates for Job
1. On job detail page, look for "Recommended Candidates" or "AI Matches"
2. **Expected Result**: Shows ranked list of candidates with match scores

```bash
# API verification
JOB_ID="<uuid-of-job>"
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8888/api/v1/recruiting/matching/jobs/$JOB_ID/matching-candidates?limit=10" | jq '.'
```

#### Step 4.2: View Matching Jobs for Candidate
1. On candidate profile, look for "Matching Jobs" section
2. **Expected Result**: Shows jobs ranked by fit score

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8888/api/v1/recruiting/matching/candidates/$CANDIDATE_ID/matching-jobs" | jq '.'
```

#### Step 4.3: Test Hybrid Matching (LLM Rerank)
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8888/api/v1/recruiting/matching/hybrid/jobs/$JOB_ID/matching-candidates?use_llm_rerank=true&limit=5" | jq '.'
```
**Expected**: Returns candidates with `reasoning` field explaining the match.

#### Step 4.4: Check Matching Config
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/matching/config | jq '.'
```

---

### Phase 5: Duplicate Detection & Merge Queue (15 minutes)

#### Step 5.1: Trigger Duplicate Detection
If you added John Smith and David Brown (same skills, similar profile), the system should detect them as potential duplicates.

```bash
# Scan for duplicates
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8888/api/v1/recruiting/merge-queue/scan?limit=100&add_to_queue=true" | jq '.'
```

#### Step 5.2: View Merge Queue
1. Navigate to: `http://localhost:3002/recruiting/merge-queue` (if page exists)
2. Or use API:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/merge-queue | jq '.'
```

**Expected Result**: Shows pending duplicate pairs with match scores and reasons.

#### Step 5.3: Review Duplicate Pair
1. Click on a pending merge item
2. View side-by-side comparison of candidates
3. **Expected Result**: Shows both profiles with match reasons (email match, name similarity, etc.)

```bash
# Get specific item detail
ITEM_ID="<merge-queue-item-uuid>"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/merge-queue/$ITEM_ID | jq '.'
```

#### Step 5.4: Merge Duplicates
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/recruiting/merge-queue/merge \
  -d '{
    "primary_candidate_id": "<keep-this-candidate-uuid>",
    "duplicate_candidate_id": "<merge-into-primary-uuid>",
    "merge_queue_item_id": "<item-uuid>",
    "merge_strategy": "smart_merge"
  }' | jq '.'
```

#### Step 5.5: Verify Merge Queue Stats
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/merge-queue/stats/summary | jq '.'
```

---

### Phase 6: Observations & Activity Tracking (10 minutes)

#### Step 6.1: Add Manual Observation
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/recruiting/observations/candidates/$CANDIDATE_ID/observations \
  -d '{
    "field_name": "preferred_location",
    "field_value": "Boston, MA",
    "value_type": "string",
    "extraction_method": "manual",
    "confidence": 1.0
  }' | jq '.'
```

#### Step 6.2: Add Candidate Email
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/recruiting/observations/candidates/$CANDIDATE_ID/emails \
  -d '{
    "email": "john.smith.personal@gmail.com",
    "is_primary": false,
    "source": "manual"
  }' | jq '.'
```

#### Step 6.3: View Activity Feed
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/observations/candidates/$CANDIDATE_ID/activity | jq '.'
```

#### Step 6.4: View My Recent Activity (Recruiter Dashboard)
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/observations/activity/my-recent | jq '.'
```

---

### Phase 7: Analytics & Reports (10 minutes)

**Note**: Reports are under `/recruiting/reports/` not `/recruiting/analytics/`

#### Step 7.1: Pipeline Funnel Report
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/reports/pipeline-funnel | jq '.'
```

#### Step 7.2: Time-to-Fill Report
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/reports/time-to-fill | jq '.'
```

#### Step 7.3: Source Effectiveness
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/reports/source-effectiveness | jq '.'
```

#### Step 7.4: Hiring Velocity
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/reports/hiring-velocity | jq '.'
```

#### Step 7.5: Department Breakdown
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/reports/department-breakdown | jq '.'
```

---

### Phase 8: EEO Compliance (5 minutes)

#### Step 8.1: View EEO Form Options
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/eeo/form-options | jq '.'
```

#### Step 8.2: EEO Summary Report
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/eeo/reports/summary | jq '.'
```

---

### Phase 9: Admin Configuration (10 minutes)

#### Step 9.1: View SLA Configurations
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/admin/sla-configurations | jq '.'
```

#### Step 9.2: View Scorecard Templates
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/scorecards/templates | jq '.'
```

#### Step 9.3: View Red Flag Types
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/red-flags/types | jq '.'
```

#### Step 9.4: View Offer Decline Reasons
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8888/api/v1/recruiting/offer-declines/reasons | jq '.'
```

---

## Part 3: Comprehensive API Test Script

Run this script to verify all endpoints are working:

```bash
#!/bin/bash

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMDI2YjU5MS1hMTFkLTRkYzUtYTU4ZS04MjFkMzJkNDk2MTIiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6ImFkbWluQGJoY29ycC5jb20iLCJyb2xlIjoiaHJfYWRtaW4iLCJpYXQiOjE3NjU3NTgwODMsImV4cCI6MTc2NjM2Mjg4M30.qJko0-PLn0bKaTq1WulNGDsY2AyYCIE6HwVLpsY7g7w"
BASE="http://localhost:8888/api/v1"

echo "=========================================="
echo "HRM-CORE RECRUITING E2E API TEST"
echo "=========================================="

echo -e "\n1. JOBS"
echo "   GET /recruiting/jobs"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/jobs | jq '.items | length' | xargs echo "   Jobs count:"

echo -e "\n2. CANDIDATES"
echo "   GET /recruiting/candidates"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/candidates | jq '.items | length' | xargs echo "   Candidates count:"

echo -e "\n3. MATCHING CONFIG"
echo "   GET /recruiting/matching/config"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/matching/config | jq '{skills_weight, embedding_weight}'

echo -e "\n4. MERGE QUEUE"
echo "   GET /recruiting/merge-queue"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/merge-queue | jq '{total, stats}'

echo -e "\n5. MERGE QUEUE STATS"
echo "   GET /recruiting/merge-queue/stats/summary"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/merge-queue/stats/summary | jq '.'

echo -e "\n6. MY RECENT ACTIVITY"
echo "   GET /recruiting/observations/activity/my-recent"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/observations/activity/my-recent | jq 'length' | xargs echo "   Activity events:"

echo -e "\n7. ANALYTICS - DASHBOARD SUMMARY"
echo "   GET /recruiting/analytics/dashboard-summary"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/analytics/dashboard-summary | jq '.'

echo -e "\n8. ANALYTICS - PIPELINE FUNNEL"
echo "   GET /recruiting/analytics/pipeline-funnel"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/analytics/pipeline-funnel | jq 'keys'

echo -e "\n9. EEO FORM OPTIONS"
echo "   GET /recruiting/eeo/form-options"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/eeo/form-options | jq 'keys'

echo -e "\n10. ADMIN - SLA CONFIGURATIONS"
echo "    GET /admin/sla-configurations"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/admin/sla-configurations | jq 'type'

echo -e "\n11. SCORECARD TEMPLATES"
echo "    GET /recruiting/scorecards/templates"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/scorecards/templates | jq 'type'

echo -e "\n12. RED FLAG TYPES"
echo "    GET /recruiting/red-flags/types"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/red-flags/types | jq 'type'

echo -e "\n13. OFFER DECLINE REASONS"
echo "    GET /recruiting/offer-declines/reasons"
curl -s -H "Authorization: Bearer $TOKEN" $BASE/recruiting/offer-declines/reasons | jq 'type'

echo -e "\n=========================================="
echo "TEST COMPLETE"
echo "=========================================="
```

---

## Part 4: Expected Test Results Summary

| Test | Endpoint | Expected Status | Expected Response |
|------|----------|-----------------|-------------------|
| Jobs List | GET /recruiting/jobs | 200 | `{"items": [...], "total": N}` |
| Candidates List | GET /recruiting/candidates | 200 | `{"items": [...], "total": N}` |
| Matching Config | GET /recruiting/matching/config | 200 | Config object with weights |
| Merge Queue | GET /recruiting/merge-queue | 200 | `{"items": [], "total": 0, ...}` |
| Merge Stats | GET /recruiting/merge-queue/stats/summary | 200 | Stats object |
| Activity | GET /recruiting/observations/activity/my-recent | 200 | Array of events |
| Dashboard | GET /recruiting/analytics/dashboard-summary | 200 | Summary metrics |
| Pipeline Funnel | GET /recruiting/analytics/pipeline-funnel | 200 | Stage counts |
| EEO Options | GET /recruiting/eeo/form-options | 200 | Form field options |
| SLA Config | GET /admin/sla-configurations | 200 | SLA config array |
| Scorecard Templates | GET /recruiting/scorecards/templates | 200 | Templates array |
| Red Flags | GET /recruiting/red-flags/types | 200 | Flag types array |
| Decline Reasons | GET /recruiting/offer-declines/reasons | 200 | Reasons array |

---

## Part 5: Known Limitations & Notes

1. **LLM Extraction**: Requires OpenAI API key configured in backend `.env`
2. **Embedding Matching**: Requires embeddings to be generated for candidates and jobs
3. **pgvector**: Must be enabled in Supabase for similarity search
4. **Merge Queue**: Requires candidates with similar data to trigger duplicate detection

---

## Part 6: Sample Resume for Testing

Create a file `test_resume.txt` with this content for manual upload testing:

```
JOHN SMITH
Software Engineer
john.smith@email.com | 555-0101 | Boston, MA | linkedin.com/in/johnsmith

SUMMARY
Senior Software Engineer with 5+ years of experience building scalable web applications.
Expertise in Python, React, and AWS cloud services.

EXPERIENCE

Senior Software Engineer | TechCorp Inc. | Jan 2021 - Present
- Led development of microservices architecture serving 10M+ users
- Implemented CI/CD pipelines reducing deployment time by 60%
- Mentored team of 4 junior developers

Software Engineer | StartupXYZ | Jun 2018 - Dec 2020
- Built React frontend for SaaS platform
- Developed RESTful APIs using Python/FastAPI
- Managed AWS infrastructure (EC2, RDS, S3)

EDUCATION
B.S. Computer Science | MIT | 2018
GPA: 3.8/4.0

SKILLS
Languages: Python, JavaScript, TypeScript, SQL
Frameworks: React, FastAPI, Django, Node.js
Cloud: AWS (EC2, S3, RDS, Lambda), Docker, Kubernetes
Tools: Git, Jira, Terraform, GitHub Actions
```

---

## Troubleshooting

### Issue: 401 Unauthorized
**Solution**: Token expired. Generate new token:
```bash
python3 -c "
import jwt
from datetime import datetime, timedelta

payload = {
    'sub': 'd026b591-a11d-4dc5-a58e-821d32d49612',
    'tenant_id': '9931b057-954f-4ca8-a259-5242463f13bc',
    'email': 'admin@bhcorp.com',
    'role': 'hr_admin',
    'iat': datetime.utcnow(),
    'exp': datetime.utcnow() + timedelta(days=7)
}
token = jwt.encode(payload, 'super-secret-jwt-key-change-in-production', algorithm='HS256')
print(token)
"
```

### Issue: 500 Internal Server Error
**Solution**: Check backend logs for stack trace. Common causes:
- Missing database table (run migration)
- Supabase connection issue
- Missing environment variable

### Issue: Empty responses
**Solution**: Database may not have seed data. Create test data via API or portal.

---

## Contact

For issues with this testing plan, check the backend logs:
```bash
tail -f /home/goofe/hrai/backend/logs/app.log
```

Or view real-time uvicorn output in the terminal running the backend.

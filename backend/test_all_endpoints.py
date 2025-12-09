#!/usr/bin/env python3
"""Comprehensive API test script for all sprints."""

import requests
import json

BASE_URL = "http://localhost:8888/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMDI2YjU5MS1hMTFkLTRkYzUtYTU4ZS04MjFkMzJkNDk2MTIiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6ImFkbWluQGJoY29ycC5jb20iLCJyb2xlIjoiaHJfYWRtaW4iLCJpYXQiOjE3NjUyMTY3MzUsImV4cCI6MTc2NTMwMzEzNX0.sD-pDLCEYyj4SRcLhnv5tATi7X0L9YsuAzWjj_DqZAQ"

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

results = {"passed": 0, "failed": 0, "errors": []}


def test_endpoint(name, method, endpoint, expected_status=200, data=None):
    """Test an endpoint and print result."""
    global results
    try:
        url = f"{BASE_URL}{endpoint}"
        if method == "GET":
            resp = requests.get(url, headers=HEADERS, timeout=15)
        elif method == "POST":
            resp = requests.post(url, headers=HEADERS, json=data, timeout=15)
        elif method == "PATCH":
            resp = requests.patch(url, headers=HEADERS, json=data, timeout=15)
        elif method == "DELETE":
            resp = requests.delete(url, headers=HEADERS, timeout=15)
        else:
            print(f"  [{name}] UNKNOWN METHOD")
            return

        if resp.status_code == expected_status:
            print(f"  [PASS] {name} - Status: {resp.status_code}")
            results["passed"] += 1
        else:
            print(f"  [FAIL] {name} - Expected: {expected_status}, Got: {resp.status_code}")
            results["failed"] += 1
            results["errors"].append(f"{name}: Expected {expected_status}, got {resp.status_code}")
            if resp.status_code >= 400:
                try:
                    print(f"         Error: {resp.json().get('detail', resp.text[:100])}")
                except:
                    print(f"         Error: {resp.text[:100]}")
    except Exception as e:
        print(f"  [ERROR] {name} - {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"{name}: {str(e)}")


print("=" * 60)
print("COMPREHENSIVE API TEST SUITE")
print("=" * 60)

# Health Check - Note: health endpoint is at root, not under /api/v1
print("\n--- Health Check ---")
resp = requests.get("http://localhost:8888/health", timeout=15)
if resp.status_code == 200:
    print("  [PASS] Health Check - Status: 200")
    results["passed"] += 1
else:
    print(f"  [FAIL] Health Check - Expected: 200, Got: {resp.status_code}")
    results["failed"] += 1
    results["errors"].append(f"Health Check: Expected 200, got {resp.status_code}")

# SPRINT 1-2: Core APIs
print("\n--- SPRINT 1-2: Core APIs ---")
print("\nJobs API:")
test_endpoint("List Jobs", "GET", "/recruiting/jobs")
test_endpoint("Get Specific Job", "GET", "/recruiting/jobs/f138a896-3b78-4556-b370-d0b93ff2fa25")

print("\nCandidates API:")
test_endpoint("List Candidates", "GET", "/recruiting/candidates")

print("\nApplications API:")
test_endpoint("List Applications", "GET", "/recruiting/applications")

print("\nPipeline API:")
test_endpoint("Pipeline Overview", "GET", "/recruiting/pipeline/jobs/overview")

print("\nTasks API:")
test_endpoint("List Tasks", "GET", "/recruiting/tasks")

print("\nAssignments API:")
test_endpoint("My Assignments", "GET", "/recruiting/assignments/my-assignments")

print("\nAdmin Config API:")
test_endpoint("SLA Configurations", "GET", "/admin/sla-configurations")
test_endpoint("Pipeline Templates", "GET", "/admin/pipeline-templates")
test_endpoint("Disposition Reasons", "GET", "/admin/disposition-reasons")
test_endpoint("Application Sources", "GET", "/admin/application-sources")

# SPRINT 3: Resume APIs
print("\n--- SPRINT 3: Resume APIs ---")
# Get a candidate to test with
resp = requests.get(f"{BASE_URL}/recruiting/candidates", headers=HEADERS)
candidates = resp.json().get("items", [])
if candidates:
    candidate_id = candidates[0]["id"]
    test_endpoint(f"List Resumes for Candidate", "GET", f"/recruiting/resumes/candidates/{candidate_id}/resumes")
else:
    print("  [SKIP] No candidates available")

# SPRINT 4: AI Matching APIs
print("\n--- SPRINT 4: AI Matching APIs ---")
resp = requests.get(f"{BASE_URL}/recruiting/jobs", headers=HEADERS)
jobs = resp.json().get("items", [])
if jobs:
    job_id = jobs[0]["id"]
    test_endpoint("Matching Candidates for Job", "GET", f"/recruiting/matching/jobs/{job_id}/matching-candidates?limit=5")
    test_endpoint("Recommended Candidates", "GET", f"/recruiting/matching/jobs/{job_id}/recommended")

if candidates:
    candidate_id = candidates[0]["id"]
    test_endpoint("Matching Jobs for Candidate", "GET", f"/recruiting/matching/candidates/{candidate_id}/matching-jobs")
    test_endpoint("Candidate Embedding Status", "GET", f"/recruiting/matching/embeddings/candidate/{candidate_id}/status")

if jobs:
    job_id = jobs[0]["id"]
    test_endpoint("Job Embedding Status", "GET", f"/recruiting/matching/embeddings/job/{job_id}/status")

# SPRINT 5: Dayforce Integration
print("\n--- SPRINT 5: Dayforce Integration ---")
test_endpoint("Dayforce Status", "GET", "/integrations/dayforce/status")
test_endpoint("All Integrations Status", "GET", "/integrations/status")
test_endpoint("Test Dayforce Connection", "POST", "/integrations/dayforce/test")

# SPRINT 6: Bulk Operations & Offers
print("\n--- SPRINT 6: Bulk Operations & Offers ---")
test_endpoint("List Offers", "GET", "/recruiting/offers")

# SPRINT 7: Reports & Dashboards
print("\n--- SPRINT 7: Reports & Dashboards ---")
test_endpoint("Dashboard Summary", "GET", "/recruiting/reports/dashboard")
test_endpoint("Pipeline Funnel", "GET", "/recruiting/reports/pipeline-funnel")
test_endpoint("Time to Fill", "GET", "/recruiting/reports/time-to-fill")
test_endpoint("Source Effectiveness", "GET", "/recruiting/reports/source-effectiveness")
test_endpoint("Hiring Velocity", "GET", "/recruiting/reports/hiring-velocity")
test_endpoint("Department Breakdown", "GET", "/recruiting/reports/department-breakdown")
test_endpoint("Recruiter Performance", "GET", "/recruiting/reports/recruiter-performance")
test_endpoint("SLA Overview", "GET", "/recruiting/reports/sla-overview")

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print(f"Passed: {results['passed']}")
print(f"Failed: {results['failed']}")
print(f"Total:  {results['passed'] + results['failed']}")

if results["errors"]:
    print("\nFailed Tests:")
    for err in results["errors"]:
        print(f"  - {err}")
else:
    print("\nAll tests passed!")

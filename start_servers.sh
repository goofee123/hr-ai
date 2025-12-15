#!/bin/bash

# =============================================================================
# HRM-Core Server Startup Script
# =============================================================================
# This script starts both backend (port 8888) and frontend (port 3002) servers
# It also provides test credentials for different user personas
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=8888
FRONTEND_PORT=3002
BACKEND_DIR="/home/goofe/hrai/backend"
FRONTEND_DIR="/home/goofe/hrai/frontend"

# =============================================================================
# TEST USER CREDENTIALS
# =============================================================================
# These credentials are for testing different user personas in the portal
# =============================================================================

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}       HRM-CORE TEST USER CREDENTIALS       ${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

echo -e "${GREEN}1. HR ADMIN (Full Access)${NC}"
echo "   Email:    admin@bhcorp.com"
echo "   Password: admin123"
echo "   Role:     hr_admin"
echo "   Can do:   Everything - jobs, candidates, settings, reports"
echo ""

echo -e "${GREEN}2. RECRUITER (Standard Recruiter)${NC}"
echo "   Email:    recruiter@bhcorp.com"
echo "   Password: recruiter123"
echo "   Role:     recruiter"
echo "   Can do:   Manage candidates, view jobs, submit feedback"
echo ""

echo -e "${GREEN}3. HIRING MANAGER (Department Manager)${NC}"
echo "   Email:    manager@bhcorp.com"
echo "   Password: manager123"
echo "   Role:     hiring_manager"
echo "   Can do:   View candidates for their jobs, submit scorecards"
echo ""

echo -e "${GREEN}4. INTERVIEWER (Limited View)${NC}"
echo "   Email:    interviewer@bhcorp.com"
echo "   Password: interviewer123"
echo "   Role:     interviewer"
echo "   Can do:   View assigned candidates, submit feedback only"
echo ""

echo -e "${YELLOW}=============================================${NC}"
echo -e "${YELLOW}       JWT TOKENS FOR API TESTING           ${NC}"
echo -e "${YELLOW}=============================================${NC}"
echo ""

# Generate tokens (valid for 7 days)
# These use the JWT secret: super-secret-jwt-key-change-in-production

echo -e "${GREEN}HR Admin Token:${NC}"
echo 'export TOKEN_ADMIN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMDI2YjU5MS1hMTFkLTRkYzUtYTU4ZS04MjFkMzJkNDk2MTIiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6ImFkbWluQGJoY29ycC5jb20iLCJyb2xlIjoiaHJfYWRtaW4iLCJpYXQiOjE3NjU3Njc1NjMsImV4cCI6MTc2NjM3MjM2M30.zHXLEEcBxrnXaW4rGdabFKqAFqEIXUjFYVIO1hcy42o"'
echo ""

echo -e "${GREEN}Recruiter Token:${NC}"
echo 'export TOKEN_RECRUITER="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMTI3OGE4NC05YmMzLTRlZTUtYTNhMi0xNDc2M2M4MTNmOWYiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6InJlY3J1aXRlckBiaGNvcnAuY29tIiwicm9sZSI6InJlY3J1aXRlciIsImlhdCI6MTc2NTc2NzU2MywiZXhwIjoxNzY2MzcyMzYzfQ.n5d_kwapdhWC_KIXWyZQezbG4-00pDo-tp-V4W9EiF4"'
echo ""

echo -e "${GREEN}Hiring Manager Token:${NC}"
echo 'export TOKEN_MANAGER="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxYzU4MDA0Ni1mMGJjLTQ5ODYtODJjOS02YjYwZjFiNzEzNDYiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6Im1hbmFnZXJAYmhjb3JwLmNvbSIsInJvbGUiOiJoaXJpbmdfbWFuYWdlciIsImlhdCI6MTc2NTc2NzU2MywiZXhwIjoxNzY2MzcyMzYzfQ.ecY75QPmRF_0CMbYLZADZAuOHIEPh-9-n1x_U5lRKGM"'
echo ""

echo -e "${GREEN}Interviewer Token:${NC}"
echo 'export TOKEN_INTERVIEWER="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmZTFjMDMyZC1iNDMzLTRmZTItOGViMS0zNWY1ZWExNDllMTYiLCJ0ZW5hbnRfaWQiOiI5OTMxYjA1Ny05NTRmLTRjYTgtYTI1OS01MjQyNDYzZjEzYmMiLCJlbWFpbCI6ImludGVydmlld2VyQGJoY29ycC5jb20iLCJyb2xlIjoicmVjcnVpdGVyIiwiaWF0IjoxNzY1NzY3NTYzLCJleHAiOjE3NjYzNzIzNjN9.4CQSJQaS_iQG04LNs9WfPf0JFK9PiN34RwgFEHsjmCU"'
echo "(Note: interviewer has 'recruiter' role in DB - 'interviewer' role not in DB enum)"
echo ""

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}          STARTING SERVERS                  ${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# =============================================================================
# KILL EXISTING PROCESSES
# =============================================================================

echo -e "${YELLOW}Stopping existing processes...${NC}"

# Kill any process on backend port
if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
    echo "  Killing processes on port $BACKEND_PORT..."
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Kill any process on frontend port
if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
    echo "  Killing processes on port $FRONTEND_PORT..."
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo -e "${GREEN}  Done!${NC}"
echo ""

# =============================================================================
# START BACKEND
# =============================================================================

echo -e "${YELLOW}Starting Backend Server on port $BACKEND_PORT...${NC}"
cd "$BACKEND_DIR"

# Activate virtual environment and start uvicorn
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload > /tmp/backend.log 2>&1 &
BACKEND_PID=$!

echo "  Backend PID: $BACKEND_PID"
echo "  Log file: /tmp/backend.log"

# Wait for backend to start
echo "  Waiting for backend to initialize..."
sleep 5

# Check if backend is running
if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
    echo -e "${GREEN}  Backend is running!${NC}"
else
    echo -e "${RED}  Backend may still be starting... Check /tmp/backend.log${NC}"
fi
echo ""

# =============================================================================
# START FRONTEND
# =============================================================================

echo -e "${YELLOW}Starting Frontend Server on port $FRONTEND_PORT...${NC}"
cd "$FRONTEND_DIR"

# Start Next.js dev server
nohup npm run dev -- -p $FRONTEND_PORT > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!

echo "  Frontend PID: $FRONTEND_PID"
echo "  Log file: /tmp/frontend.log"

# Wait for frontend to start
echo "  Waiting for frontend to initialize..."
sleep 10

# Check if frontend is running
if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
    echo -e "${GREEN}  Frontend is running!${NC}"
else
    echo -e "${YELLOW}  Frontend may still be compiling... Check /tmp/frontend.log${NC}"
fi
echo ""

# =============================================================================
# SUMMARY
# =============================================================================

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}            SERVERS STARTED                 ${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""
echo -e "${GREEN}Backend API:${NC}     http://localhost:$BACKEND_PORT"
echo -e "${GREEN}API Docs:${NC}        http://localhost:$BACKEND_PORT/docs"
echo -e "${GREEN}Frontend Portal:${NC} http://localhost:$FRONTEND_PORT"
echo ""
echo -e "${YELLOW}View Logs:${NC}"
echo "  Backend:  tail -f /tmp/backend.log"
echo "  Frontend: tail -f /tmp/frontend.log"
echo ""
echo -e "${YELLOW}Stop Servers:${NC}"
echo "  ./stop_servers.sh"
echo "  OR"
echo "  lsof -ti:$BACKEND_PORT | xargs kill -9"
echo "  lsof -ti:$FRONTEND_PORT | xargs kill -9"
echo ""
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}     QUICK API TEST (using admin token)     ${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""
echo "# Test health endpoint:"
echo "curl http://localhost:$BACKEND_PORT/health"
echo ""
echo "# Test jobs endpoint:"
echo 'curl -H "Authorization: Bearer $TOKEN_ADMIN" http://localhost:'$BACKEND_PORT'/api/v1/recruiting/jobs'
echo ""
echo -e "${GREEN}Happy Testing! 🚀${NC}"

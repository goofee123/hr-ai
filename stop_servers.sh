#!/bin/bash

# =============================================================================
# HRM-Core Server Stop Script
# =============================================================================
# This script stops both backend (port 8888) and frontend (port 3002) servers
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=8888
FRONTEND_PORT=3002

echo -e "${YELLOW}=============================================${NC}"
echo -e "${YELLOW}       STOPPING HRM-CORE SERVERS            ${NC}"
echo -e "${YELLOW}=============================================${NC}"
echo ""

# Kill backend
echo -e "${YELLOW}Stopping Backend (port $BACKEND_PORT)...${NC}"
if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null
    echo -e "${GREEN}  Backend stopped!${NC}"
else
    echo -e "${GREEN}  Backend was not running${NC}"
fi

# Kill frontend
echo -e "${YELLOW}Stopping Frontend (port $FRONTEND_PORT)...${NC}"
if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null
    echo -e "${GREEN}  Frontend stopped!${NC}"
else
    echo -e "${GREEN}  Frontend was not running${NC}"
fi

echo ""
echo -e "${GREEN}All servers stopped!${NC}"
echo ""
echo "To restart, run: ./start_servers.sh"

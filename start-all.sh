#!/usr/bin/env bash
# ==============================================================================
# SEO-AD AutoPilot - Start All (API + Web Console) Concurrently (macOS/Linux)
# ==============================================================================
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Robust PATH auto-discovery for node, pnpm, git, and python under various shells
for path_dir in "/usr/local/bin" "/opt/homebrew/bin" "$HOME/.local/share/pnpm" "$HOME/.bun/bin" "/usr/bin" "/bin" "/usr/sbin" "/sbin"; do
    if [ -d "$path_dir" ]; then
        export PATH="$path_dir:$PATH"
    fi
done

# Resolve pnpm from global npm bin prefix if still missing
if ! command -v pnpm &> /dev/null && command -v npm &> /dev/null; then
    NPM_GLOBAL_BIN=$(npm config get prefix 2>/dev/null)/bin
    if [ -d "$NPM_GLOBAL_BIN" ]; then
        export PATH="$NPM_GLOBAL_BIN:$PATH"
    fi
fi

echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}      Starting SEO-AD AutoPilot Complete Suite  ${NC}"
echo -e "${GREEN}               API (8000) + Web (3000)          ${NC}"
echo -e "${BLUE}================================================${NC}"

# Verify critical environment components
echo -e "${YELLOW}[INFO] Verifying development environment...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}[ERROR] Node.js is not found in PATH. Please install Node.js (v18+) to continue.${NC}"
    exit 1
fi
if ! command -v pnpm &> /dev/null; then
    echo -e "${YELLOW}[WARN] pnpm is not found. Attempting fallback to npm...${NC}"
    USE_NPM=true
else
    USE_NPM=false
fi

# Handle graceful shutdown of background jobs on Ctrl+C
cleanup() {
    echo
    echo -e "${YELLOW}[INFO] Stopping all services...${NC}"
    # Kill the background process groups/pids
    kill $(jobs -p) 2>/dev/null || true
    echo -e "${GREEN}[OK] Services stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start API Server in background
echo -e "${BLUE}[1/2] Starting API Server on http://127.0.0.1:8000...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "apps/api/.venv" ]; then
    source apps/api/.venv/bin/activate
fi

python3 -m uvicorn apps.api.seo_ad_autopilot.app:create_app --factory --host 127.0.0.1 --port 8000 > /dev/null 2>&1 &
API_PID=$!

# Wait briefly for API to initialize
sleep 2

# Start Web Console in background
echo -e "${BLUE}[2/2] Starting Web Console on http://localhost:3000...${NC}"
if [ "$USE_NPM" = true ]; then
    npm --prefix apps/web run dev &
else
    pnpm --dir apps/web dev &
fi
WEB_PID=$!

echo -e "${GREEN}[SUCCESS] Both services are running! Press Ctrl+C to terminate both.${NC}"
echo -e "  - API Docs:      http://127.0.0.1:8000/docs"
echo -e "  - Web Interface: http://localhost:3000"
echo

# Wait for background processes
wait

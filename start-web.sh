#!/usr/bin/env bash
# ==============================================================================
# SEO-AD AutoPilot - Start Web Console only (macOS/Linux)
# ==============================================================================
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

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}   Starting SEO-AD AutoPilot Web Console   ${NC}"
echo -e "${BLUE}========================================${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}[ERROR] Node.js is not found in PATH. Please install Node.js (v18+) to continue.${NC}"
    exit 1
fi

if ! command -v pnpm &> /dev/null; then
    echo -e "${YELLOW}[WARN] pnpm is not found. Attempting fallback to npm...${NC}"
    npm --prefix apps/web run dev
else
    pnpm --dir apps/web dev
fi

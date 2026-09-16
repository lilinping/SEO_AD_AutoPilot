#!/usr/bin/env bash
# ==============================================================================
# SEO-AD AutoPilot - Start API Server only (macOS/Linux)
# ==============================================================================
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Robust PATH auto-discovery for node, pnpm, git, and python under various shells
for path_dir in "/usr/local/bin" "/opt/homebrew/bin" "$HOME/.local/share/pnpm" "$HOME/.bun/bin" "/usr/bin" "/bin" "/usr/sbin" "/sbin"; do
    if [ -d "$path_dir" ]; then
        export PATH="$path_dir:$PATH"
    fi
done

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}   Starting SEO-AD AutoPilot API Server   ${NC}"
echo -e "${BLUE}========================================${NC}"

if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "apps/api/.venv" ]; then
    source apps/api/.venv/bin/activate
fi

# Start uvicorn
python3 -m uvicorn apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000

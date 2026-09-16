#!/usr/bin/env bash
# ==============================================================================
# SEO-AD AutoPilot - macOS/Linux Setup Script (Developer & User Convenience)
# ==============================================================================
set -e

# ANSI Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   SEO-AD AutoPilot - Setup Wizard (macOS/Linux)   ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo

# ------------------------------------------------------------------------------
# Robust PATH Auto-Discovery
# ------------------------------------------------------------------------------
# Before checking commands, inject common installation directories into PATH
for path_dir in "/usr/local/bin" "/opt/homebrew/bin" "$HOME/.local/share/pnpm" "$HOME/.bun/bin" "/usr/bin" "/bin" "/usr/sbin" "/sbin"; do
    if [ -d "$path_dir" ] && [[ ":$PATH:" != *":$path_dir:"* ]]; then
        export PATH="$path_dir:$PATH"
    fi
done

# Resolve pnpm from global npm bin prefix if still missing
if ! command -v pnpm &> /dev/null && command -v npm &> /dev/null; then
    NPM_GLOBAL_BIN=$(npm config get prefix 2>/dev/null)/bin
    if [ -d "$NPM_GLOBAL_BIN" ] && [[ ":$PATH:" != *":$NPM_GLOBAL_BIN:"* ]]; then
        export PATH="$NPM_GLOBAL_BIN:$PATH"
    fi
fi

# ------------------------------------------------------------------------------
# Dependency Pre-checks
# ------------------------------------------------------------------------------
# Check Git
if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}[WARNING] git not found. Please install git if you plan to use CMS/GitHub deployments.${NC}"
else
    echo -e "${GREEN}[OK] Found Git: $(git --version)${NC}"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] python3 not found. Please install Python 3.9+ and try again.${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Found Python: $(python3 --version)${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}[ERROR] Node.js not found. Please install Node.js (v18+) to run the frontend.${NC}"
    echo -e "${YELLOW}[TIP] Recommended installation: nvm (https://github.com/nvm-sh/nvm) or Homebrew (brew install node)${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Found Node.js: $(node --version)${NC}"

# Check/Install pnpm
if ! command -v pnpm &> /dev/null; then
    echo -e "${YELLOW}[INFO] pnpm not found in PATH.${NC}"
    if command -v npm &> /dev/null; then
        echo -e "${BLUE}[INFO] Attempting to install pnpm globally via npm...${NC}"
        npm install -g pnpm || {
            echo -e "${YELLOW}[WARNING] Failed to install pnpm globally. We will fall back to using npm for dependency installation.${NC}"
            USE_NPM=true
        }
    else
        echo -e "${RED}[ERROR] Neither pnpm nor npm was found. Please install a Node.js package manager.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[OK] Found pnpm: $(pnpm --version)${NC}"
    USE_NPM=false
fi

# ------------------------------------------------------------------------------
# Project Setup Steps
# ------------------------------------------------------------------------------

# Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo -e "${BLUE}[INFO] Creating Python virtual environment (.venv)...${NC}"
    python3 -m venv .venv
else
    echo -e "${GREEN}[OK] Virtual environment (.venv) already exists.${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}[INFO] Activating virtual environment...${NC}"
source .venv/bin/activate

# Upgrade pip
echo -e "${BLUE}[INFO] Upgrading pip...${NC}"
pip install --upgrade pip

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}[INFO] Installing Python dependencies (from requirements.txt)...${NC}"
    pip install -r requirements.txt
else
    echo -e "${YELLOW}[WARNING] requirements.txt not found. Skipping Python package installation.${NC}"
fi

# Install Node.js dependencies
if [ -d "apps/web" ]; then
    echo -e "${BLUE}[INFO] Installing Node.js frontend dependencies...${NC}"
    if [ "$USE_NPM" = true ]; then
        npm --prefix apps/web install
    else
        pnpm install
    fi
else
    echo -e "${YELLOW}[WARNING] Frontend directory apps/web not found. Skipping frontend installation.${NC}"
fi

# Setup env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${BLUE}[INFO] Copying .env.example to .env...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}[WARNING] Created .env. Please configure your API/Provider keys in it before running.${NC}"
    else
        echo -e "${YELLOW}[WARNING] .env.example not found. Creating a blank .env file...${NC}"
        touch .env
    fi
else
    echo -e "${GREEN}[OK] .env file already exists.${NC}"
fi

echo
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}   Setup Completed Successfully!                    ${NC}"
echo -e "${GREEN}====================================================${NC}"
echo
echo -e "To start the SEO-AD AutoPilot service:"
echo -e "  - Start All (API + Web Console): ${YELLOW}./start-all.sh${NC}"
echo -e "  - Start API Server only:        ${YELLOW}./start-api.sh${NC}"
echo -e "  - Start Web Console only:       ${YELLOW}./start-web.sh${NC}"
echo

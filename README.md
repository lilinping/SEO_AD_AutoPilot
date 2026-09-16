# SEO-AD AutoPilot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)

> Automated SEO analysis, content strategy, ad optimization, and deployment pipeline — with human-in-the-loop approval gates.

## Overview

SEO-AD AutoPilot is an open-source platform that automates the full SEO-AD lifecycle: site crawling, diagnostics, content strategy, ad safety auditing, technical SEO patching, and controlled deployment with rollback capabilities.

中文说明文档：[`docs/功能完善与验收说明.md`](docs/功能完善与验收说明.md) 记录了当前功能完善范围、成熟产品对标结论、验收 gate、Provider 证据缺口、视觉农场生产化缺口和后续优先级。

**Key principles:**
- 🛡️ **White-hat first** — preview before execute, explain every action
- 🔍 **Transparent** — full audit trail, structured approval gates
- 🔄 **Reversible** — one-click rollback on any deployment
- 🧩 **Modular** — plug in your own providers, models, and workflows

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Next.js Console                        │
│   Overview · Projects · Strategy · Quality · Approvals   │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Control Plane                    │
│   Workflow · Approval Gate · Monitoring · Rollback       │
└──────┬───────────────┬───────────────────┬──────────────┘
       │               │                   │
┌──────▼──────┐ ┌──────▼──────┐ ┌─────────▼─────────┐
│   Crawlers  │ │  Analyzers  │ │    Providers       │
│ Playwright  │ │ SEO · GEO   │ │ GitHub · CMS · AD  │
│ HTTP · UA   │ │ Ad · Market │ │ Script · Alert     │
└─────────────┘ └─────────────┘ └───────────────────┘
```

## Features

### Core Pipeline
- **Site Profiling** — Crawl, screenshot, extract meta/headings/links/images, build SiteProfile
- **Content Strategy** — Topic clusters, content calendar, trend/news/qa multi-source research
- **Ad Safety** — Ad slot auditing, A/B/C/D readiness levels, no-ad recommendations
- **Technical SEO** — Meta/schema/heading patching with audit trail
- **Deployment** — GitHub PR, CMS Draft, Script writeback with approval gating
- **Monitoring** — Regression tracking, runtime health, automated alerts
- **Rollback** — One-click revert with deployment history

### Control Console
- Dashboard overview with project portfolio
- Strategy and acceptance surfaces
- Approval workflow with bulk operations
- Visual regression tracking
- Settings and provider configuration

### Integrations
- **Search Engines**: Google, Bing, Yandex, DuckDuckGo, Baidu, Naver, Seznam
- **Ad Networks**: AdSense, GAM, Mediavine, Ezoic, Freestar, and more
- **Providers**: GitHub, CMS, Script API, Search Console, GA4
- **Alerts**: PagerDuty, Opsgenie, Linear, Asana, Slack, Discord, Teams, and 20+ more
- **LLMs**: OpenAI, Anthropic, Google, DeepSeek (optional)

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- pnpm
- Redis (optional, for production queue)

### 1. Clone & Setup

```bash
git clone https://github.com/lilinping/SEO_AD_AutoPilot.git
cd SEO_AD_AutoPilot
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pnpm install
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pnpm install
```

### 2. Configure

**macOS / Linux:**

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your settings (see [Configuration](#configuration) below).

### 3. Run

**macOS / Linux (requires `make`):**

```bash
make api-dev      # Start API server at :8000
make web-dev      # Start web console at :3000
make seed         # Seed demo workspace
```

**Windows (no `make` required):**

Option A - Use batch scripts (recommended):

```powershell
.\setup.bat      # First time: install dependencies
.\start-api.bat  # Start API server
.\start-web.bat  # Start web console (in another terminal)
```

Option B - Manual commands:

```powershell
# Start API server
.venv\Scripts\uvicorn.exe apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000

# Start web console (in another terminal)
pnpm --dir apps/web dev

# Seed demo workspace
.venv\Scripts\python.exe -m apps.api.seo_ad_autopilot.seed
```

Open http://localhost:3000 to access the console.

### Docker Deployment

```bash
docker-compose up -d
```

This starts API (port 8000), Redis, and Web console (port 3000).

## Configuration

All configuration is via environment variables. See [`.env.example`](.env.example) for the full list.

### Essential

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite fallback |
| `SEO_AD_BOT_API_KEY` | API authentication key | `dev-key` |
| `SEO_AD_BOT_DEFAULT_WORKSPACE` | Default workspace ID | `demo-pack` |

### Providers (optional)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for LLM features |
| `TAVILY_API_KEY` | Tavily for web research |
| `SEO_AD_BOT_GITHUB_TOKEN` | GitHub PR writeback |
| `SEO_AD_BOT_CMS_PROVIDER_URL` | CMS draft endpoint |

### Behavior

| Variable | Description | Default |
|----------|-------------|---------|
| `SEO_AD_BOT_ENABLE_BROWSER_CRAWL` | Enable Playwright crawling | `false` |
| `SEO_AD_BOT_AUTO_DEPLOY_ENABLED` | Auto-deploy after approval | `true` |
| `SEO_AD_BOT_APPROVAL_REQUIRED_THRESHOLD` | Risk score requiring approval | `60` |
| `SEO_AD_BOT_BLOCK_AUTO_DEPLOY_THRESHOLD` | Risk score blocking auto-deploy | `80` |

## API Reference

The FastAPI control plane exposes a REST API at `http://localhost:8000/api`.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/overview` | Workspace status and summary |
| GET | `/api/projects` | List all projects |
| POST | `/api/projects/{id}/sync` | Trigger project sync |
| GET | `/api/projects/{id}/content-strategy` | Content strategy report |
| GET | `/api/projects/{id}/ad-audit` | Ad safety audit |
| GET | `/api/projects/{id}/technical-seo` | Technical SEO report |
| POST | `/api/tasks/{id}/approve` | Approve a task |
| POST | `/api/tasks/{id}/deploy` | Deploy changes |
| POST | `/api/tasks/{id}/rollback` | Rollback deployment |
| GET | `/api/regressions` | Regression test results |
| GET | `/api/alerts` | Active alerts |

Authentication: `X-API-Key` header or `Authorization: Bearer <key>`.

Full API documentation available at `http://localhost:8000/docs` (Swagger UI).

## CLI

```bash
# Analyze a website
python seo_ad_cli.py analyze https://example.com

# Run full audit
python seo_ad_cli.py audit https://example.com --output report.json
```

## Development

### Project Structure

```
seo-ad-autopilot/
├── apps/
│   ├── api/              # FastAPI control plane
│   │   ├── seo_ad_autopilot/
│   │   │   ├── app.py    # FastAPI app factory
│   │   │   ├── agents/   # GEO, SEO, Ad agents
│   │   │   ├── crawlers/ # Playwright, HTTP crawlers
│   │   │   └── providers/# GitHub, CMS, Script connectors
│   │   └── tests/        # API tests
│   ├── web/              # Next.js console
│   └── worker/           # Background task worker
├── packages/
│   ├── contracts/        # Shared TypeScript types
│   └── skill-registry/   # Skill plugin registry
├── docs/                 # Documentation
├── docker-compose.yml    # Docker orchestration
└── Makefile              # Development commands
```

### Available Commands

**macOS / Linux (via Make):**

```bash
make api-dev       # Start API server with hot-reload
make api-test      # Run API tests
make web-dev       # Start Next.js dev server
make web-build     # Build Next.js for production
make web-typecheck # Type-check frontend code
make seed          # Seed demo workspace data
make worker        # Start background worker
make test          # Run all tests
```

**Windows (PowerShell):**

```powershell
# API server
.venv\Scripts\uvicorn.exe apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000

# API tests
.venv\Scripts\python.exe -m unittest apps.api.tests.test_smoke_unittest -v

# Web console
pnpm --dir apps/web dev

# Build
pnpm --dir apps/web build

# Type-check
pnpm --dir apps/web typecheck

# Seed
.venv\Scripts\python.exe -m apps.api.seo_ad_autopilot.seed

# Worker
.venv\Scripts\python.exe -m apps.worker.main

# All tests
.venv\Scripts\python.exe -m unittest apps.api.tests.test_smoke_unittest -v
```

### Running Tests

```bash
# Unit tests
make test

# Or directly
.venv/bin/python -m unittest apps.api.tests.test_smoke_unittest -v
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Visual Farm Acceptance

Install the pinned Chromium runtime into the project workspace, then run a real
two-page screenshot gate. Both target hosts must be listed in
`SEO_AD_BOT_VISUAL_FARM_ALLOWED_HOSTS`.

```bash
make visual-farm-browser-install
SEO_AD_BOT_VISUAL_FARM_ALLOWED_HOSTS=www.example.com,preview.example.com \
SEO_AD_BOT_VISUAL_FARM_SMOKE_BASELINE_URL=https://www.example.com/page \
SEO_AD_BOT_VISUAL_FARM_SMOKE_PREVIEW_URL=https://preview.example.com/page \
SEO_AD_BOT_VISUAL_FARM_SMOKE_MAX_DIFF_PERCENT=2 \
make visual-farm-smoke
```

The command stores validated PNG files and a JSON report under
`var/visual-farm/smoke/`. Missing targets, a missing browser, capture failures,
invalid PNG artifacts, and threshold violations all return a non-zero exit code.

## Runtime Edge Deployment

The bundled runtime edge accepts versioned route snapshots from the control
plane, persists them under `var/runtime-edge/`, and keeps the previous snapshot
available for rollback. Configure the same secret on both services:

```bash
SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL=http://runtime-edge:8080/deploy
SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN=replace-me
SEO_AD_BOT_EDGE_API_KEY=replace-me
```

Production can require every published host to resolve and present a valid TLS
certificate before a new snapshot is activated:

```bash
SEO_AD_BOT_EDGE_VERIFY_DNS_TLS=true
SEO_AD_BOT_EDGE_EXPECTED_PUBLIC_IPS=203.0.113.10,2001:db8::10
```

The protected runtime endpoints are `POST /deploy`, `POST /rollback`,
`GET /deployments`, `GET /deployments/{id}`, and `GET /readyz`. Project-scoped
publishes merge into the active multi-site snapshot; requests are routed by Host
and longest `publicPath`, with that prefix removed before reverse proxying.

## Stripe Connect Settlement

The billing control plane can execute official Stripe Connect Transfers without
an intermediary HTTP gateway. Enable it explicitly and provide a restricted
secret through the production secret manager:

```bash
SEO_AD_BOT_BILLING_GATEWAY_STRIPE_ADAPTER=stripe_sdk
SEO_AD_BOT_BILLING_GATEWAY_STRIPE_SECRET_KEY=sk_live_...
```

Live execution requires `destinationType=connected_account`, a connected account
in `destinationRef`, and a stable `metadata.idempotencyKey`. SDK errors are
recorded as failed or blocked settlement executions and never fall back to a
synthetic success. The default `http` adapter remains available for other
provider gateways.

## Maintenance status

2026-09-16: CI checks are now blocking for lint, unit/integration/smoke tests,
Docker builds, and dependency auditing. The maintained baseline is the
`chore/green-baseline` branch, which is ready to merge into `main` after the
required checks pass.

## Roadmap

- [ ] Production-grade Playwright crawling service
- [ ] Redis queue for async task orchestration
- [ ] PostgreSQL migration and object storage
- [ ] OpenTelemetry + Sentry observability
- [ ] Multi-model LLM routing gateway
- [ ] Visual regression farm production deployment
- [ ] Real ad network settlement integration (Stripe Connect SDK complete; additional providers pending)
- [ ] A/B experiment framework
- [x] Multi-site edge deployment orchestration (production DNS/TLS cutover still environment-specific)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [Next.js](https://nextjs.org/), [Playwright](https://playwright.dev/)
- Inspired by white-hat SEO automation practices

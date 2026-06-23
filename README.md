# SEO-AD AutoPilot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)

> Automated SEO analysis, content strategy, ad optimization, and deployment pipeline — with human-in-the-loop approval gates.

## Overview

SEO-AD AutoPilot is an open-source platform that automates the full SEO-AD lifecycle: site crawling, diagnostics, content strategy, ad safety auditing, technical SEO patching, and controlled deployment with rollback capabilities.

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
git clone https://github.com/YOUR_USERNAME/seo-ad-autopilot.git
cd seo-ad-autopilot

# Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or: pip install fastapi uvicorn httpx playwright

# Node.js dependencies
pnpm install
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your settings (see Configuration below)
```

### 3. Run

```bash
# Start API server
make api-dev

# Start web console (in another terminal)
make web-dev

# Seed demo workspace
make seed
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

## Roadmap

- [ ] Production-grade Playwright crawling service
- [ ] Redis queue for async task orchestration
- [ ] PostgreSQL migration and object storage
- [ ] OpenTelemetry + Sentry observability
- [ ] Multi-model LLM routing gateway
- [ ] Visual regression farm production deployment
- [ ] Real ad network settlement integration
- [ ] A/B experiment framework
- [ ] Multi-site edge deployment orchestration

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [Next.js](https://nextjs.org/), [Playwright](https://playwright.dev/)
- Inspired by white-hat SEO automation practices

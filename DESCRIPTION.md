# SEO-AD AutoPilot

> 🚀 White-hat SEO automation with human-in-the-loop approval gates.

SEO-AD AutoPilot is an open-source platform that automates the full SEO and ad optimization lifecycle — from site crawling and diagnostics to content strategy, ad safety auditing, and controlled deployment with one-click rollback.

## Why SEO-AD AutoPilot?

Most SEO tools give you a report and leave you to figure out the rest. SEO-AD AutoPilot goes further: it **analyzes**, **suggests**, **prepares**, and **deploys** — but only after you approve. Every action is transparent, every deployment is reversible, and every decision is auditable.

## Core Capabilities

| Feature | Description |
|---------|-------------|
| 🔍 **Site Profiling** | Crawl with Playwright, extract meta/headings/links/images, build structured SiteProfile |
| 📊 **Multi-Engine Analysis** | Google, Bing, Yandex, DuckDuckGo, Baidu + GEO (ChatGPT, Perplexity, Claude) |
| 📝 **Content Strategy** | Topic clusters, content calendar, trend/news/qa multi-source research |
| 🛡️ **Ad Safety Audit** | Ad slot detection, A/B/C/D readiness levels, no-ad recommendations |
| 🔧 **Technical SEO** | Meta/schema/heading patching with audit trail |
| 🚀 **Controlled Deploy** | GitHub PR, CMS Draft, Script writeback with approval gating |
| 🔄 **One-Click Rollback** | Revert any deployment instantly |
| 📈 **Monitoring & Alerts** | Regression tracking, runtime health, 20+ alert integrations |

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

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/seo-ad-autopilot.git
cd seo-ad-autopilot

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pnpm install
cp .env.example .env

# Run
make api-dev    # API at :8000
make web-dev    # Console at :3000
make seed       # Demo workspace
```

Or with Docker:
```bash
docker-compose up -d
```

## Key Principles

- **White-hat first** — preview before execute, explain every action
- **Transparent** — full audit trail, structured approval gates
- **Reversible** — one-click rollback on any deployment
- **Modular** — plug in your own providers, models, and workflows

## Built With

- **Backend**: FastAPI, Python 3.9+, SQLite/PostgreSQL
- **Frontend**: Next.js 14, React, TypeScript
- **Crawling**: Playwright, httpx
- **Queue**: Redis (optional)
- **Monitoring**: OpenTelemetry (planned)

## Integrations

- **Search Engines**: Google, Bing, Yandex, DuckDuckGo, Baidu, Naver, Seznam
- **GEO Engines**: ChatGPT, Perplexity, Claude
- **Ad Networks**: AdSense, GAM, Mediavine, Ezoic, Freestar, Raptive, Monumetric
- **Providers**: GitHub, CMS, Script API, Search Console, GA4
- **Alerts**: PagerDuty, Opsgenie, Splunk, Grafana, Linear, Asana, Slack, Discord, Teams, Jira, and 20+ more

## Roadmap

- [ ] Production-grade Playwright crawling service
- [ ] Redis queue for async task orchestration
- [ ] PostgreSQL migration and object storage
- [ ] OpenTelemetry + Sentry observability
- [ ] Multi-model LLM routing gateway
- [ ] Visual regression farm production deployment
- [ ] Real ad network settlement integration
- [ ] A/B experiment framework

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.

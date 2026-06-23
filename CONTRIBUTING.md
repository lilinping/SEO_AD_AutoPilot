# Contributing to SEO-AD AutoPilot

Thank you for considering contributing to SEO-AD AutoPilot! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- pnpm
- Redis (optional, for production queue)

### Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/seo-ad-autopilot.git
   cd seo-ad-autopilot
   ```

3. Set up the development environment:
   ```bash
   # Python virtual environment
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

   # Node.js dependencies
   pnpm install

   # Configure
   cp .env.example .env
   ```

4. Start the development servers:
   ```bash
   make api-dev   # API server at http://localhost:8000
   make web-dev   # Web console at http://localhost:3000
   ```

## Development Workflow

### Branch Naming

- `feature/<name>` — New features
- `fix/<name>` — Bug fixes
- `docs/<name>` — Documentation changes
- `refactor/<name>` — Code refactoring

### Commit Messages

Use clear, descriptive commit messages:
- `feat: add new ad network connector`
- `fix: resolve approval gate timeout`
- `docs: update API reference`
- `refactor: simplify workflow service`

### Code Style

**Python:**
- Follow PEP 8
- Use type hints
- Keep functions focused and concise

**TypeScript/React:**
- Use functional components with hooks
- Follow existing naming conventions
- Run `pnpm --dir apps/web typecheck` before committing

### Testing

Before submitting a PR:

```bash
# Run all tests
make test

# Type-check frontend
make web-typecheck
```

### Pull Request Process

1. Create a feature branch from `main`
2. Make your changes in small, focused commits
3. Ensure all tests pass
4. Update documentation if needed
5. Submit a PR with a clear description of changes
6. Wait for CI checks and review

### What to Contribute

**High-value contributions:**
- New provider integrations (CMS, ad networks, alert services)
- Improved crawl reliability and anti-bot handling
- Visual regression testing improvements
- Documentation and examples
- Bug fixes and performance improvements

**Areas needing help:**
- Production Playwright deployment
- Redis queue orchestration
- PostgreSQL migration tooling
- OpenTelemetry instrumentation
- Multi-model LLM routing

## Code of Conduct

- Be respectful and constructive
- Focus on technical merit
- Help newcomers feel welcome
- No tolerance for harassment

## Questions?

Open an issue for bugs or feature requests. For general questions, start a discussion on GitHub.

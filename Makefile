.PHONY: api web api-dev api-test web-dev web-build web-typecheck test seed worker visual-farm-browser-install visual-farm-smoke

PLAYWRIGHT_BROWSERS_PATH ?= $(CURDIR)/var/playwright

api: api-dev

web: web-dev

api-dev:
	./.venv/bin/uvicorn apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000

api-test:
	./.venv/bin/python -m unittest discover -s apps/api/tests -p 'test_*.py' -v

web-dev:
	pnpm --dir apps/web dev

web-build:
	pnpm --dir apps/web build

web-typecheck:
	pnpm --dir apps/web typecheck

seed:
	./.venv/bin/python -m apps.api.seo_ad_autopilot.seed

worker:
	./.venv/bin/python -m apps.worker.main

visual-farm-browser-install:
	PLAYWRIGHT_BROWSERS_PATH="$(PLAYWRIGHT_BROWSERS_PATH)" ./.venv/bin/python -m playwright install chromium

visual-farm-smoke:
	PLAYWRIGHT_BROWSERS_PATH="$(PLAYWRIGHT_BROWSERS_PATH)" ./.venv/bin/python -m apps.visual_farm.smoke

test: api-test

.PHONY: api-dev api-test web-dev web-build web-typecheck test seed worker

api-dev:
	./.venv/bin/uvicorn apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000

api-test:
	./.venv/bin/python -m unittest apps.api.tests.test_smoke_unittest -v

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

test: api-test

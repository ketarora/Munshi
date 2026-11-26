# Munshi developer commands.
# Windows: default venv path. macOS/Linux: make PY=.venv/bin/python

PY ?= .venv/Scripts/python.exe
PYTHON ?= python
API ?= http://127.0.0.1:8000
TOKEN ?= demo-child-token

.PHONY: install test api web dev typecheck build e2e audit reset-demo verify-audit eval demo

install:
	$(PYTHON) -m venv .venv
	$(PY) -m pip install -r requirements.txt
	cd apps/web && npm install

test:
	$(PY) -m pytest

eval:
	$(PY) -m pytest tests/test_nlu.py -q

api:
	$(PY) apps/api/run.py

web:
	cd apps/web && npm run dev

typecheck:
	cd apps/web && npx tsc --noEmit

build:
	cd apps/web && npm run build

e2e:
	cd apps/web && npm run e2e

audit:
	cd apps/web && npm audit --audit-level=high
	$(PY) -m pip check

# Full stack in containers (config provided; verify Docker on your machine).
dev:
	docker compose up --build

reset-demo:
	curl -s -X POST $(API)/api/demo/reset
	@echo

verify-audit:
	curl -s -H "X-Munshi-Token: $(TOKEN)" $(API)/api/audit

demo:
	@echo "1. Open http://127.0.0.1:3000"
	@echo "2. Start call -> 'बिजली का बिल भर दो' -> 'हाँ'"
	@echo "3. 'रामू को 5,000 भेज दे' -> refused, child notified"
	@echo "4. 'पानी का बिल' -> child approval -> approve"
	@echo "5. Under the hood -> rule, amount source, audit chain"

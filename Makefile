# Material Setu — dev shortcuts
# Defaults to local PostgreSQL on port 5432 (or override with environment variable)

export DATABASE_URL ?= postgresql://postgres:9950@127.0.0.1:5432/material_setu
export MATERIAL_SETU_DEMO ?= 1

VENV := backend/.venv

.PHONY: help db migrate venv seed reset api ui test

help:
	@echo "make db       - start PostgreSQL (Docker)"
	@echo "make migrate  - apply db/migrations/*.sql to a running database"
	@echo "make venv     - create backend virtualenv + install deps"
	@echo "make seed     - wipe + load the sample CPSE dataset, run matching, play steward decisions"
	@echo "make api      - run the FastAPI backend on :8000"
	@echo "make ui       - run the React dashboard on :5173"
	@echo "make test     - run backend tests"

db:
	docker compose up -d db

migrate:
	@for f in db/migrations/*.sql; do \
		echo "applying $$f"; \
		docker compose exec -T db psql -U material_setu -d material_setu < $$f; \
	done

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -r backend/requirements.txt pytest httpx

seed:
	$(VENV)/bin/python scripts/seed.py --reset

reset:
	@TOKEN=$$(curl -s http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' \
		-d '{"email":"admin@material-setu.gov.in","password":"materialsetu"}' \
		| sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'); \
	curl -s -X POST http://127.0.0.1:8000/admin/reset -H "Authorization: Bearer $$TOKEN" && echo

api:
	cd backend && ../$(VENV)/bin/uvicorn app.main:app --reload --port 8000

ui:
	cd frontend && npm install && npm run dev

test:
	cd backend && ../$(VENV)/bin/python -m pytest -q

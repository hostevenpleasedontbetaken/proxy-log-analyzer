# Shortcuts for common commands. Each one is a plain docker command you can run directly.
.PHONY: up down reset logs test test-backend test-frontend test-samples samples lint

up: ## Start everything (http://localhost:5173)
	docker compose up --build

down: ## Stop everything, keep data
	docker compose down

reset: ## Stop everything and DELETE the local database
	docker compose down -v

logs: ## Follow the api logs
	docker compose logs -f api

test: test-backend test-frontend test-samples

test-backend:
	docker compose run --rm --build api pytest -q

test-frontend:
	docker compose run --rm --no-deps web sh -c "npm install --no-audit --no-fund && npm test"

# The sample generator is standard-library Python only, so a stock Python image is enough.
SAMPLES_PYTHON = docker run --rm -v "$(CURDIR)/samples:/samples" -w /samples python:3.13-slim

test-samples:
	$(SAMPLES_PYTHON) python -m unittest discover -s tests -t .

samples: ## Regenerate the committed sample logs and answer keys
	$(SAMPLES_PYTHON) python build_samples.py

lint:
	docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
	docker compose run --rm --no-deps web sh -c "npm install --no-audit --no-fund && npm run lint && npm run typecheck"

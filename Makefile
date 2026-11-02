# Shortcuts for common commands. Each one is a plain docker command you can run directly.
.PHONY: up down reset logs test test-backend test-frontend test-samples samples evaluate lint \
	cloud-setup cloud-secrets deploy

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

evaluate: ## Re-measure detection on the samples and rewrite docs/RESULTS.md
	docker compose run --rm --no-deps -T api python -m app.evaluation > docs/RESULTS.md

lint:
	docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
	docker compose run --rm --no-deps web sh -c "npm install --no-audit --no-fund && npm run lint && npm run typecheck"

# --- production (Google Cloud + Firebase); see docs/DEPLOY.md ---------------------------

cloud-setup: ## One-time: APIs, image registry, service account, empty secrets
	infra/gcp/setup.sh

cloud-secrets: ## Store the Neon connection strings in Secret Manager (hidden input)
	infra/gcp/set-secrets.sh

deploy: ## Build the image, migrate, deploy the API and the frontend
	infra/gcp/deploy.sh

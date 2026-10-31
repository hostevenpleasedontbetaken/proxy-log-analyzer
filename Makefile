# Shortcuts for common commands. Each one is a plain docker compose command you can run directly.
.PHONY: up down reset logs test test-backend test-frontend lint

up: ## Start everything (http://localhost:5173)
	docker compose up --build

down: ## Stop everything, keep data
	docker compose down

reset: ## Stop everything and DELETE the local database
	docker compose down -v

logs: ## Follow the api logs
	docker compose logs -f api

test: test-backend test-frontend

test-backend:
	docker compose run --rm --build api pytest -q

test-frontend:
	docker compose run --rm --no-deps web sh -c "npm install --no-audit --no-fund && npm test"

lint:
	docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
	docker compose run --rm --no-deps web sh -c "npm install --no-audit --no-fund && npm run lint && npm run typecheck"

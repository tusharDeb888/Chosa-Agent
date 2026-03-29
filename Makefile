.PHONY: help up down logs migrate seed test-unit test-integration test-e2e replay-dlq clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─────────────────── Docker ───────────────────

up: ## Start all services
	docker compose up -d --build

up-monitoring: ## Start all services including monitoring
	docker compose --profile monitoring up -d --build

down: ## Stop all services
	docker compose down

down-clean: ## Stop all services and remove volumes
	docker compose down -v

logs: ## Tail all service logs
	docker compose logs -f

logs-backend: ## Tail backend logs only
	docker compose logs -f backend

# ─────────────────── Database ───────────────────

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add users table")
	cd backend && alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed mock portfolio data
	cd backend && python -m scripts.seed_mock_portfolio

# ─────────────────── Testing ───────────────────

test-unit: ## Run unit tests
	cd backend && python -m pytest tests/unit -v --tb=short

test-integration: ## Run integration tests (requires Docker Compose up)
	cd backend && python -m pytest tests/integration -v --tb=short

test-e2e: ## Run end-to-end tests
	cd backend && python -m pytest tests/e2e -v --tb=short

test: ## Run all tests
	cd backend && python -m pytest tests/ -v --tb=short

# ─────────────────── Operations ───────────────────

replay-dlq: ## Replay dead-letter queue events
	cd backend && python -m scripts.replay_events

# ─────────────────── Cleanup ───────────────────

clean: ## Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

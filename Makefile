.PHONY: install dev lint format typecheck test test-all docker-build clean help

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────

install: ## Install production dependencies
	pip install -e .

dev: ## Install with dev dependencies
	pip install -e ".[dev]"
	pre-commit install

# ── Quality ──────────────────────────────────────────────────

lint: ## Run linter (ruff check)
	ruff check src/ tests/ --fix

format: ## Run formatter (ruff format)
	ruff format src/ tests/

typecheck: ## Run type checker (mypy)
	mypy src/ --ignore-missing-imports

quality: lint format typecheck ## Run all quality checks

# ── Testing ──────────────────────────────────────────────────

test: ## Run unit tests (no Azure creds needed)
	pytest tests/ -v -m "not integration" --tb=short

test-cov: ## Run unit tests with coverage
	pytest tests/ -v -m "not integration" --cov=src --cov-report=term-missing

test-all: ## Run all tests including integration (requires Azure creds)
	pytest tests/ -v --tb=short

# ── Docker ───────────────────────────────────────────────────

docker-build: ## Build Docker image
	docker build -t anf-foundry-selfops:latest .

docker-run: ## Run Docker container (requires .env file)
	docker run --rm -it --env-file .env anf-foundry-selfops:latest

# ── Infrastructure ───────────────────────────────────────────

deploy: ## Deploy Azure infrastructure via Bicep
	az deployment group create \
		--resource-group $${ANF_RESOURCE_GROUP} \
		--template-file infra/main.bicep \
		--parameters infra/parameters.json

validate-bicep: ## Validate Bicep template
	az bicep build --file infra/main.bicep

# ── Application ──────────────────────────────────────────────

run: ## Run the agent interactively
	python -m src.main

# ── Cleanup ──────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

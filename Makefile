.PHONY: help install dev lint typecheck test test-cov run dry-run docker-build docker-up docker-down clean

PYTHON ?= python3
PIP ?= pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install package
	$(PIP) install -e .

dev: ## Install with dev dependencies
	$(PIP) install -e ".[dev]"
	pre-commit install

lint: ## Run linter (ruff)
	ruff check src/ tests/
	ruff format --check src/ tests/

format: ## Auto-format code
	ruff check --fix src/ tests/
	ruff format src/ tests/

typecheck: ## Run type checker (mypy)
	mypy src/

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage report
	pytest --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

run: ## Run the bridge (requires env vars)
	wu-mqtt-bridge run

dry-run: ## Fetch weather without publishing (requires WU_GEOCODE)
	wu-mqtt-bridge run --dry-run

docker-build: ## Build Docker image
	docker build -t wu-mqtt-bridge .

docker-up: ## Start local stack (Mosquitto + bridge)
	docker compose up --build

docker-down: ## Stop local stack
	docker compose down

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info htmlcov/ .coverage coverage.xml .mypy_cache .pytest_cache .ruff_cache

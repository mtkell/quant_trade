.PHONY: help install install-dev test lint format type-check clean docker-build docker-up docker-down docs

help:
	@echo "Coinbase Spot Trading Engine - Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install           Install production dependencies"
	@echo "  make install-dev       Install development dependencies (includes testing, linting, formatting)"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test              Run full test suite"
	@echo "  make test-cov          Run tests with coverage report"
	@echo "  make test-integration  Run integration tests only"
	@echo "  make lint              Run linter (ruff) and security checks"
	@echo "  make format            Auto-format code with black and isort"
	@echo "  make type-check        Run mypy type checking"
	@echo "  make check             Run all checks (lint, type-check, test)"
	@echo ""
	@echo "Development:"
	@echo "  make clean             Remove generated files and caches"
	@echo "  make docs              Generate Sphinx documentation"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build      Build Docker image"
	@echo "  make docker-up         Start services with docker-compose"
	@echo "  make docker-down       Stop docker-compose services"
	@echo ""
	@echo "Code Generation:"
	@echo "  make version           Show current version"
	@echo "  make pre-commit-install Install pre-commit hooks"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev,monitoring]"
	pre-commit install

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=trading --cov-report=html --cov-report=term-missing

test-integration:
	pytest tests/ -v -m integration

lint:
	ruff check trading/ tests/ scripts/ examples/
	black --check trading/ tests/ scripts/ examples/

format:
	isort trading/ tests/ scripts/ examples/
	black trading/ tests/ scripts/ examples/
	ruff check --fix trading/ tests/ scripts/ examples/

type-check:
	mypy trading/ --ignore-missing-imports

check: lint type-check test
	@echo "✓ All checks passed"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -delete
	rm -rf build/ dist/ .pytest_cache/ .mypy_cache/ htmlcov/ .coverage
	rm -rf .ruff_cache/

docs:
	cd docs && sphinx-build -b html -d _build/doctrees . _build/html
	@echo "Documentation built in docs/_build/html/index.html"

docker-build:
	docker build -t quant-trade:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

version:
	@python -c "import trading; print('quant-trade v0.1.0')" || echo "quant-trade v0.1.0"

pre-commit-install:
	pre-commit install
	@echo "✓ Pre-commit hooks installed"

.DEFAULT_GOAL := help

# Project shortcuts
.PHONY: help dev test lint format db-status migrate seed prod down

PYTHON_SOURCES = apps core scripts tests alembic main.py

help:
	@echo "Available targets:"
	@echo "  make dev         Start the development Compose stack"
	@echo "  make test        Run pytest in the test Compose environment"
	@echo "  make lint        Run flake8"
	@echo "  make format      Format Python and sort imports"
	@echo "  make db-status   Show dev database migration status"
	@echo "  make migrate     Apply dev database migrations"
	@echo "  make seed        Insert demo data into the dev database"
	@echo "  make prod        Start the production Compose stack"
	@echo "  make down        Stop the development Compose stack"

# Docker Compose workflows
dev:
	@echo "Starting development stack..."
	docker compose -f docker-compose.dev.yml up --build -d

test:
	@echo "Running tests in the test container..."
	docker compose -f docker-compose.test.yml run --build --rm api python -m pytest -q

prod:
	@echo "Starting production stack..."
	docker compose -f docker-compose.prod.yml up --build -d

down:
	@echo "Stopping development stack..."
	docker compose -f docker-compose.dev.yml down

# Linting and formatting
lint:
	@echo "Running linter..."
	flake8 $(PYTHON_SOURCES)

format:
	@echo "Formatting code and fixing selected lint issues..."
	isort --profile black --line-length 79 $(PYTHON_SOURCES)
	black --line-length 79 $(PYTHON_SOURCES)

# Database migration commands
db-status:
	@echo "Checking dev database migration status..."
	docker compose -f docker-compose.dev.yml exec api alembic current
	@echo "Migration history:"
	docker compose -f docker-compose.dev.yml exec api alembic history --verbose

migrate:
	@echo "Applying dev database migrations..."
	docker compose -f docker-compose.dev.yml exec api alembic upgrade head

seed:
	@echo "Inserting demo data into the development database..."
	docker compose -f docker-compose.dev.yml exec api python -m scripts.seed_data


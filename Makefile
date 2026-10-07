# Project automation commands
.PHONY: help dev test lint format db-status migrate seed docker-dev docker-test docker-prod

PYTHON_SOURCES = apps core scripts tests alembic main.py

help:
	@echo "Available targets:"
	@echo "  make dev         Start the local FastAPI development server"
	@echo "  make test        Run the pytest suite"
	@echo "  make lint        Run flake8"
	@echo "  make format      Format Python and sort imports"
	@echo "  make db-status   Check Alembic migration status"
	@echo "  make migrate     Apply Alembic migrations"
	@echo "  make seed        Insert demo seed data for local dev/test"
	@echo "  make docker-dev  Start the development stack with Docker Compose"
	@echo "  make docker-test Start the isolated test stack with Docker Compose"
	@echo "  make docker-prod Start the production stack with Docker Compose"

# Local development server
dev:
	@echo "Starting development server..."
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	@echo "Running pytest..."
	PYTHONPATH=. python -m pytest -q

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
	@echo "Checking database migration status..."
	alembic current
	@echo "Migration history:"
	alembic history --verbose

migrate:
	@echo "Applying Alembic migrations..."
	alembic upgrade head

seed:
	@echo "Inserting demo data into the development database..."
	docker compose -f docker-compose.dev.yml exec api python -m scripts.seed_data

# Docker commands
docker-dev:
	@echo "Starting development environment with Docker..."
	docker compose -f docker-compose.dev.yml up --build -d

docker-test:
	@echo "Starting test environment with Docker..."
	docker compose -f docker-compose.test.yml up --build -d

docker-prod:
	@echo "Starting production environment with Docker..."
	docker compose -f docker-compose.prod.yml up --build -d

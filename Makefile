# Development Commands
.PHONY: migrate migrate-dry migrate-generate db-status

# Database migration commands
migrate:
	@echo "Running database migrations..."
	python scripts/migrate.py

migrate-dry:
	@echo "Dry run - showing what would be migrated..."
	python scripts/migrate.py --dry-run

migrate-generate:
	@echo "Generating migration (without applying)..."
	python scripts/migrate.py --generate-only

db-status:
	@echo "Checking database migration status..."
	alembic current
	@echo "Migration history:"
	alembic history --verbose

# Development server
dev:
	@echo "Starting development server..."
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	@echo "Running tests..."
	pytest

# Linting and formatting
lint:
	@echo "Running linter..."
	flake8 .

format:
	@echo "Formatting code..."
	black .
	isort .

# Docker commands
docker-dev:
	@echo "Starting development environment with Docker..."
	docker-compose -f docker-compose.dev.yml up --build

docker-test:
	@echo "Starting test environment with Docker..."
	docker-compose -f docker-compose.test.yml up --build

docker-prod:
	@echo "Starting production environment with Docker..."
	docker-compose -f docker-compose.prod.yml up --build
# Development Commands
.PHONY: db-status dev test lint format docker-dev docker-test docker-prod

# Database migration commands
# Use standard Alembic commands for migration generation and application.
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
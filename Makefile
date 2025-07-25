.PHONY: help build up down logs ps clean test lint migrate shell

# Default target
help:
	@echo "Available commands:"
	@echo "  make build       - Build all Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - Show logs from all services"
	@echo "  make ps          - Show running containers"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linters"
	@echo "  make migrate     - Run database migrations"
	@echo "  make shell-api   - Open shell in API container"
	@echo "  make shell-db    - Open PostgreSQL shell"
	@echo "  make dev         - Start development environment"

# Load env files
include .env
-include .env.local

# Build Docker images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d

# Start development environment
dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Stop services
down:
	docker-compose down

# Show logs
logs:
	docker-compose logs -f

# Show specific service logs
logs-%:
	docker-compose logs -f $*

# Show running containers
ps:
	docker-compose ps

# Clean up
clean:
	docker-compose down -v
	rm -rf postgres-data redis-data
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run tests
test:
	docker-compose exec api pytest

# Run linters
lint:
	docker-compose exec api ruff check .
	docker-compose exec api black --check .
	docker-compose exec api mypy .

# Format code
format:
	docker-compose exec api black .
	docker-compose exec api ruff check --fix .

# Run database setup
migrate:
	@echo "Running database setup..."
	@echo "Applying schema..."
	@cat database/schema.sql | docker-compose exec -T postgres psql -U medical_user -d medical_data || exit 1
	@echo "Applying seed data..."
	@cat database/seeds.sql | docker-compose exec -T postgres psql -U medical_user -d medical_data || exit 1
	@echo "Database setup complete!"

# Apply all migrations without resetting database
migrate-only:
	@echo "Applying migrations..."
	@for file in database/migrations/*.sql; do \
		echo "Applying $$file..."; \
		cat $$file | docker-compose exec -T postgres psql -U medical_user -d medical_data || true; \
	done
	@echo "Migrations complete!"

# Full database reset and migration
migrate-fresh: migrate migrate-only
	@echo "Full database reset and migration complete!"


# Shell access
shell-api:
	docker-compose exec api /bin/bash

shell-db:
	docker-compose exec postgres psql -U $(DB_USER) -d medical_data

# Install pre-commit hooks
install-hooks:
	pre-commit install

# Create initial data directories
init-dirs:
	mkdir -p data/{raw,processed,logs,cache}
	mkdir -p data/raw/{clinicaltrials,pubmed,web}
	mkdir -p data/processed/{embeddings,extracted}
	mkdir -p data/logs/{scraper,processing}

# Quick setup for new developers
setup: init-dirs
	cp .env.example .env
	make build
	make up
	sleep 10  # Wait for services to start
	make migrate
	@echo "Setup complete! Edit .env file and run 'make dev' to start development."

# Monitor services
monitor:
	docker-compose exec api celery -A tasks.celery_app flower

# Backup database
backup:
	docker-compose exec postgres pg_dump -U $(DB_USER) medical_data > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql

# Restore database
restore:
	docker-compose exec -T postgres psql -U $(DB_USER) medical_data < $(file)
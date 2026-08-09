.PHONY: setup test-unit test-property test-integration lint format migrate seed-data run-local teardown

# Python environment setup
setup:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"
	docker compose up -d
	@echo "Waiting for services to be ready..."
	sleep 5
	$(MAKE) migrate
	@echo "Setup complete. Run 'make run-local' to start the application."

# Run unit tests
test-unit:
	pytest tests/unit -v --tb=short -m unit

# Run property-based tests
test-property:
	pytest tests/properties -v --tb=short -m property

# Run integration tests (requires Docker services running)
test-integration:
	pytest tests/integration -v --tb=short -m integration

# Run all tests with coverage
test:
	pytest --cov=app --cov-report=term-missing --cov-report=html

# Lint code with ruff and type-check with mypy
lint:
	ruff check app/ tests/
	mypy app/

# Format code with black and ruff
format:
	black app/ tests/
	ruff check --fix app/ tests/

# Run database migrations
migrate:
	alembic upgrade head

# Seed database with sample data
seed-data:
	python scripts/seed_data.py

# Run application locally
run-local:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tear down Docker services and clean up
teardown:
	docker compose down -v
	@echo "All services stopped and volumes removed."

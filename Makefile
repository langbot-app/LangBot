# LangBot Makefile
# Quick developer commands

.PHONY: test test-quick test-integration-fast test-coverage test-all-local lint

# Run all tests (full suite with coverage)
test:
	bash run_tests.sh

# Quick self-test for developers (lint + unit + smoke, no real credentials needed)
test-quick:
	bash scripts/test-quick.sh

# Fast integration tests (SQLite/API/Pipeline, no external services)
test-integration-fast:
	bash scripts/test-integration-fast.sh

# Coverage gate (all tests, enforces minimum threshold)
test-coverage:
	bash scripts/test-coverage.sh

# Full local quality gate (quick + integration + coverage)
test-all-local:
	bash scripts/test-quick.sh
	bash scripts/test-integration-fast.sh
	bash scripts/test-coverage.sh

# Run linting only
lint:
	ruff check src/langbot/ tests/
	ruff format --check src/langbot/ tests/

# Fix linting issues
lint-fix:
	ruff check --fix src/langbot/ tests/
	ruff format src/langbot/ tests/
# LangBot Makefile
# Quick developer commands

.PHONY: test test-quick lint

# Run all tests (full suite with coverage)
test:
	bash run_tests.sh

# Quick self-test for developers (lint + unit + smoke, no real credentials needed)
test-quick:
	bash scripts/test-quick.sh

# Run linting only
lint:
	ruff check src/langbot/ tests/
	ruff format --check src/langbot/ tests/

# Fix linting issues
lint-fix:
	ruff check --fix src/langbot/ tests/
	ruff format src/langbot/ tests/
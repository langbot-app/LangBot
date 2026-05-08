#!/bin/bash

# Quick developer self-test command
# Runs linting, unit tests, and smoke tests without requiring real provider keys
# Suitable for local branch validation

set -e

echo "=== LangBot Quick Self-Test ==="
echo ""

# 1. Ruff check
echo "[1/3] Running ruff check..."
if command -v ruff &> /dev/null; then
    ruff check src/langbot/ tests/ --quiet || {
        echo "⚠ Ruff check found issues. Run 'ruff check --fix' to auto-fix."
    }
else
    echo "⚠ ruff not installed, skipping lint check"
fi
echo ""

# 2. Unit tests
echo "[2/3] Running unit tests..."
uv run pytest tests/unit_tests/ -q --tb=short 2>&1 | tail -5
echo ""

# 3. Smoke tests (if exists)
echo "[3/3] Running smoke tests..."
if [ -d "tests/smoke" ]; then
    uv run pytest tests/smoke/ -q --tb=short 2>&1 | tail -5
else
    echo "No smoke tests found, skipping"
fi
echo ""

echo "=== Quick Self-Test Complete ==="
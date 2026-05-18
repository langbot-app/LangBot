#!/bin/bash

# Quick developer self-test command
# Runs linting, unit tests, and smoke tests without requiring real provider keys
# Suitable for local branch validation

set -euo pipefail

echo "=== LangBot Quick Self-Test ==="
echo ""

# 1. Ruff check
echo "[1/3] Running ruff check..."
uv run ruff check src/langbot/ tests/ --output-format=concise || {
    echo ""
    echo "⚠ Ruff check found issues. Run 'uv run ruff check --fix' to auto-fix."
    exit 1
}
echo "✓ Ruff check passed"
echo ""

# 2. Unit tests
echo "[2/3] Running unit tests..."
uv run pytest tests/unit_tests/ -q --tb=short
echo ""

# 3. Smoke tests (if exists)
echo "[3/3] Running smoke tests..."
if [ -d "tests/smoke" ]; then
    uv run pytest tests/smoke/ -q --tb=short
else
    echo "No smoke tests found, skipping"
fi
echo ""

echo "=== Quick Self-Test Complete ==="
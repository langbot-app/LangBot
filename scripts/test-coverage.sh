#!/bin/bash

# Coverage gate script
# Runs unit, smoke, and fast integration tests with a combined coverage threshold
# Uses separate pytest invocations to avoid sys.modules pollution between test types

set -euo pipefail

echo "=== LangBot Coverage Gate ==="
echo ""

# Minimum combined coverage for unit, smoke, and fast integration tests
COVERAGE_THRESHOLD=18

# Create temporary directory for coverage files
COV_DIR=$(mktemp -d)
trap 'rm -rf "$COV_DIR"' EXIT
export COVERAGE_FILE="$COV_DIR/.coverage"

echo "[1/3] Running unit + smoke tests with coverage..."
uv run pytest tests/unit_tests/ tests/smoke/ \
    --cov=langbot \
    --cov-report= \
    -q --tb=short
echo ""

echo "[2/3] Running fast integration tests with coverage..."
uv run pytest tests/integration/ -m "not slow" \
    --cov=langbot \
    --cov-append \
    --cov-report= \
    -q --tb=short
echo ""

echo "[3/3] Reporting combined coverage..."
uv run coverage xml -o coverage.xml
uv run coverage report --fail-under="$COVERAGE_THRESHOLD"

echo ""
echo "=== Coverage Gate Complete ==="
echo ""
echo "Coverage baseline: $COVERAGE_THRESHOLD%"
echo "Coverage report saved to coverage.xml"

#!/bin/bash

# Fast integration tests
# Runs integration tests excluding slow ones (PostgreSQL, external services)
# Uses fake runner/provider, no real credentials needed

set -euo pipefail

echo "=== LangBot Fast Integration Tests ==="
echo ""

echo "Running integration tests (excluding slow)..."
uv run pytest tests/integration/ -m "not slow" -q --tb=short

echo ""
echo "=== Fast Integration Tests Complete ==="
#!/bin/bash

# Script to run all unit tests
# This script helps avoid circular import issues by setting up the environment properly

set -e

echo "Setting up test environment..."

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Installing test dependencies..."
    pip install pytest pytest-asyncio pytest-cov
fi

echo "Running all unit tests..."

# Run tests with coverage
pytest tests/unit_tests/ -v --tb=short \
    --cov=pkg \
    --cov-report=xml \
    "$@"

echo ""
echo "Test run complete!"
echo "Coverage report saved to coverage.xml"

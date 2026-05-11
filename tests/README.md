# LangBot Test Suite

This directory contains the test suite for LangBot, with a focus on comprehensive unit testing of pipeline stages.

## Quality Gate Layers

LangBot uses a layered quality gate system for developers and CI:

| Layer | Command | What it runs | When to use |
|-------|---------|--------------|-------------|
| **Quick** | `make test-quick` or `bash scripts/test-quick.sh` | Ruff lint + Unit tests + Smoke tests | Before every commit |
| **Fast Integration** | `make test-integration-fast` or `bash scripts/test-integration-fast.sh` | SQLite/API/Pipeline integration (no external services) | Before PR, weekly |
| **Coverage Gate** | `make test-coverage` or `bash scripts/test-coverage.sh` | All tests with coverage, threshold: 18% | Before merge, CI |
| **Full Local** | `make test-all-local` | Quick + Integration + Coverage | Before major changes |

**Note**: PostgreSQL migration tests and slow tests are NOT in local default gates. They run in separate CI workflows.

### Developer Workflow

```bash
# Daily: Quick self-test
bash scripts/test-quick.sh

# Before PR: Full local gate
make test-all-local

# Or run each layer separately:
bash scripts/test-quick.sh           # ~2 min
bash scripts/test-integration-fast.sh # ~3 min
bash scripts/test-coverage.sh         # ~8 min
```

### Coverage Baseline

Current coverage threshold: **18%**
Actual coverage: **30%**

This is a conservative baseline to prevent coverage regression. It does NOT represent the final quality target. Key modules have higher coverage:
- `pipeline.preproc.preproc`: 53%
- `pipeline.process.process`: 96%
- `pipeline.respback.respback`: 88%
- `telemetry.telemetry`: 87%
- `provider.session.sessionmgr`: 100%
- `provider.tools.toolmgr`: 83%
- `storage.providers.s3storage`: 80%

## Important Note

Due to circular import dependencies in the pipeline module structure, the test files use **lazy imports** via `importlib.import_module()` instead of direct imports. This ensures tests can run without triggering circular import errors.

## Structure

```
tests/
├── __init__.py
├── factories/                    # Shared test factories
│   ├── __init__.py              # Factory exports
│   ├── app.py                   # FakeApp factory
│   ├── message.py               # Message/query factories
│   ├── provider.py              # FakeProvider factory
│   └── platform.py              # FakePlatform factory
├── integration/                  # Integration tests (real resources)
│   ├── __init__.py
│   ├── api/                     # HTTP API tests
│   │   ├── __init__.py
│   │   └── test_smoke.py        # API smoke tests
│   ├── pipeline/                # Pipeline stage-chain tests
│   │   ├── __init__.py
│   │   └── test_full_flow.py    # Full flow integration
│   └── persistence/             # Database/persistence tests
│       ├── __init__.py
│       └── test_migrations.py   # Alembic migration tests
├── smoke/                        # Smoke tests (quick validation)
│   └── test_fake_message_flow.py
├── unit_tests/                   # Unit tests
│   ├── box/                      # Box module tests
│   ├── config/                   # Configuration tests
│   ├── pipeline/                 # Pipeline stage tests
│   │   └── conftest.py          # Shared fixtures and test infrastructure
│   ├── platform/                 # Platform adapter tests
│   ├── plugin/                   # Plugin system tests
│   │   └── test_handler_actions.py # Action handler tests
│   ├── provider/                 # Provider tests
│   │   ├── test_session_manager.py # SessionManager tests
│   │   └── test_tool_manager.py    # ToolManager tests
│   ├── rag/                      # RAG tests
│   │   └── test_file_storage.py   # File/ZIP storage tests
│   ├── storage/                  # Storage tests
│   │   └── test_s3storage.py      # S3StorageProvider tests
│   ├── vector/                   # Vector tests
│   │   └── test_vdb_filter_conversion.py # VDB filter tests
│   └── telemetry/                # Telemetry tests (rewritten)
├── utils/                        # Test utilities
│   ├── __init__.py
│   └── import_isolation.py      # sys.modules isolation for circular imports
└── README.md                     # This file
```

## Test Factories

The `tests/factories/` package provides reusable test factories:

```python
from tests.factories import (
    FakeApp,          # Mock application
    FakeProvider,     # Fake LLM provider
    FakePlatform,     # Fake platform adapter
    text_query,       # Create text query
    group_text_query, # Create group query
    command_query,    # Create command query
)

# Create fake app
app = FakeApp()

# Create query with text
query = text_query("hello world")

# Create fake provider that returns specific response
provider = FakeProvider().returns("test response")

# Create fake platform for outbound capture
platform = FakePlatform()
await platform.reply_message(query.message_event, reply_chain)
outbound = platform.get_outbound_messages()
```

See `tests/factories/__init__.py` for all available factories.

## Test Architecture

### Fixtures (`conftest.py`)

The test suite uses a centralized fixture system that provides:

- **MockApplication**: Comprehensive mock of the Application object with all dependencies
- **Mock objects**: Pre-configured mocks for Session, Conversation, Model, Adapter
- **Sample data**: Ready-to-use Query objects, message chains, and configurations
- **Helper functions**: Utilities for creating results and common assertions

### Design Principles

1. **Isolation**: Each test is independent and doesn't rely on external systems
2. **Mocking**: All external dependencies are mocked to ensure fast, reliable tests
3. **Coverage**: Tests cover happy paths, edge cases, and error conditions
4. **Extensibility**: Easy to add new tests by reusing existing fixtures

## Running Tests

### Quick self-test for developers

For local branch validation without real provider keys:

```bash
make test-quick
```

or

```bash
bash scripts/test-quick.sh
```

This runs:
1. Ruff lint check
2. Unit tests
3. Smoke tests

Suitable for quick validation before committing.

### Using the test runner script (recommended for full coverage)
```bash
bash run_tests.sh
```

This script automatically:
- Activates the virtual environment
- Installs test dependencies if needed
- Runs tests with coverage
- Generates HTML coverage report

### Manual test execution

#### Run all unit tests
```bash
uv run pytest tests/unit_tests/ --cov=langbot --cov-report=xml --cov-report=term
```

#### Run specific test module
```bash
uv run pytest tests/unit_tests/pipeline/ -v
```

#### Run specific test file
```bash
uv run pytest tests/unit_tests/pipeline/test_bansess.py -v
```

#### Run with coverage
```bash
uv run pytest tests/unit_tests/pipeline/ --cov=langbot --cov-report=html
```

#### Run specific test
```bash
uv run pytest tests/unit_tests/pipeline/test_bansess.py::test_bansess_whitelist_allow -v
```

### Using markers

```bash
# Run only unit tests
uv run pytest tests/unit_tests/ -m unit

# Run only integration tests
uv run pytest tests/integration/ -m integration

# Run integration tests excluding slow ones
uv run pytest tests/integration/ -m "not slow" -q

# Skip slow tests
uv run pytest tests/unit_tests/ -m "not slow"
```

### Running integration tests

Integration tests validate real system behavior with actual database/network resources.

```bash
# Run all integration tests (excluding slow ones)
uv run pytest tests/integration/ -m "not slow" -q

# Run SQLite migration integration tests
uv run pytest tests/integration/persistence/test_migrations.py -q --tb=short

# Run API smoke integration tests
uv run pytest tests/integration/api/test_smoke.py -q

# Run pipeline full-flow integration tests
uv run pytest tests/integration/pipeline/test_full_flow.py -q

# Run with verbose output
uv run pytest tests/integration/ -v
```

Note: Integration tests use:
- Temporary databases (tmp_path) for persistence tests
- Fake app/services for API tests (no real provider/platform)
- Fake runner/provider for pipeline tests (no real LLM API)
- Do not require external services

### Running migration tests locally

SQLite migration tests can be run locally without any external dependencies:

```bash
# SQLite migration tests (uses tmp_path, no external DB needed)
uv run pytest tests/integration/persistence/test_migrations.py -q --tb=short
```

PostgreSQL migration tests require an external PostgreSQL database:

```bash
# PostgreSQL migration tests (requires PostgreSQL service)
# Tests are marked as slow and skipped if TEST_POSTGRES_URL is not set
TEST_POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/test_db \
    uv run pytest tests/integration/persistence/test_migrations_postgres.py -q --tb=short

# Or skip by default (no PostgreSQL available)
uv run pytest tests/integration/persistence/test_migrations_postgres.py -q --tb=short
# Output: SKIPPED (TEST_POSTGRES_URL not set)
```

Note: PostgreSQL tests are **not** included in fast integration gate because they:
- Require external PostgreSQL service
- Are marked with `@pytest.mark.slow`
- Need `TEST_POSTGRES_URL` environment variable

CI workflow `.github/workflows/test-migrations.yml` runs:
- SQLite tests in `test-migrations-sqlite` job (fast, no external services)
- PostgreSQL tests in `test-migrations-postgres` job (uses PostgreSQL service container)

### Running pipeline integration tests locally

Pipeline full-flow integration tests validate real stage interactions:

```bash
# Run pipeline integration tests (uses fake runner, no real LLM API)
uv run pytest tests/integration/pipeline/test_full_flow.py -q --tb=short

# Run with coverage for pipeline modules
uv run pytest tests/integration/pipeline \
    --cov=langbot.pkg.pipeline.preproc.preproc \
    --cov=langbot.pkg.pipeline.process.process \
    --cov=langbot.pkg.pipeline.respback.respback \
    --cov-report=term -q
```

These tests:
- Use `FakeRunner` class to simulate LLM responses without real API calls
- Import real `PreProcessor`, `MessageProcessor`, `SendResponseBackStage` stages
- Validate stage chain: PreProcessor → Processor → SendResponseBackStage
- Test prevent_default, exception handling, and full message flow
- Do not require real LLM provider keys

### Known Issues

Some tests may encounter circular import errors. This is a known issue with the current module structure. The test infrastructure is designed to work around this using lazy imports, but if you encounter issues:

1. Make sure you're running from the project root directory
2. Ensure dependencies are installed: `uv sync --dev`
3. Try running a simple test first to verify the test infrastructure works

## CI/CD Integration

Tests are automatically run on:
- Pull request opened
- Pull request marked ready for review
- Push to PR branch
- Push to master/develop branches

The workflow runs tests on Python 3.11, 3.12, and 3.13 to ensure compatibility.

## Adding New Tests

### 1. For a new pipeline stage

Create a new test file `test_<stage_name>.py`:

```python
"""
<StageName> stage unit tests
"""

import pytest
from langbot.pkg.pipeline.<module>.<stage> import <StageClass>
from langbot.pkg.pipeline import entities as pipeline_entities


@pytest.mark.asyncio
async def test_stage_basic_flow(mock_app, sample_query):
    """Test basic flow"""
    stage = <StageClass>(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, '<StageName>')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
```

### 2. For additional fixtures

Add new fixtures to the appropriate `conftest.py`:

```python
@pytest.fixture
def my_custom_fixture():
    """Description of fixture"""
    return create_test_data()
```

### 3. For test data

Use the helper functions in `conftest.py`:

```python
from tests.unit_tests.pipeline.conftest import create_stage_result, assert_result_continue

result = create_stage_result(
    result_type=pipeline_entities.ResultType.CONTINUE,
    query=sample_query
)

assert_result_continue(result)
```

## Best Practices

1. **Test naming**: Use descriptive names that explain what's being tested
2. **Arrange-Act-Assert**: Structure tests clearly with setup, execution, and verification
3. **One assertion per test**: Focus each test on a single behavior
4. **Mock appropriately**: Mock external dependencies, not the code under test
5. **Use fixtures**: Reuse common test data through fixtures
6. **Document tests**: Add docstrings explaining what each test validates

## Troubleshooting

### Import errors
Make sure you've installed the package in development mode:
```bash
uv sync --dev
```

### Async test failures
Ensure you're using `@pytest.mark.asyncio` decorator for async tests.

### Mock not working
Check that you're mocking at the right level and using `AsyncMock` for async functions.

## Future Enhancements

- [x] Add integration tests for database migrations (SQLite)
- [x] Add PostgreSQL migration integration tests (G-003)
- [x] Add integration tests for full pipeline execution
- [x] Add API smoke integration tests
- [ ] Add E2E tests
- [ ] Add performance benchmarks
- [ ] Add mutation testing for better coverage quality
- [ ] Add property-based testing with Hypothesis
# LangBot Test Suite

This directory contains the test suite for LangBot, with a focus on comprehensive unit testing of pipeline stages.

## Structure

```
tests/
├── pipeline/           # Pipeline stage tests
│   ├── conftest.py    # Shared fixtures and test infrastructure
│   ├── test_preproc.py
│   ├── test_ratelimit.py
│   ├── test_bansess.py
│   ├── test_respback.py
│   ├── test_resprule.py
│   └── test_pipelinemgr.py
└── README.md          # This file
```

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

### Run all tests
```bash
pytest
```

### Run pipeline tests only
```bash
pytest tests/pipeline/
```

### Run specific test file
```bash
pytest tests/pipeline/test_preproc.py
```

### Run with coverage
```bash
pytest tests/pipeline/ --cov=pkg/pipeline --cov-report=html
```

### Run specific test
```bash
pytest tests/pipeline/test_preproc.py::test_preproc_basic_flow -v
```

## CI/CD Integration

Tests are automatically run on:
- Pull request opened
- Pull request marked ready for review
- Push to PR branch
- Push to master/develop branches

The workflow runs tests on Python 3.10, 3.11, and 3.12 to ensure compatibility.

## Adding New Tests

### 1. For a new pipeline stage

Create a new test file `test_<stage_name>.py`:

```python
"""
<StageName> stage unit tests
"""

import pytest
from pkg.pipeline.<module>.<stage> import <StageClass>
from pkg.pipeline import entities as pipeline_entities


@pytest.mark.asyncio
async def test_stage_basic_flow(mock_app, sample_query):
    """Test basic flow"""
    stage = <StageClass>(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, '<StageName>')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
```

### 2. For additional fixtures

Add new fixtures to `conftest.py`:

```python
@pytest.fixture
def my_custom_fixture():
    """Description of fixture"""
    return create_test_data()
```

### 3. For test data

Use the helper functions in `conftest.py`:

```python
from tests.pipeline.conftest import create_stage_result, assert_result_continue

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
uv pip install -e .
```

### Async test failures
Ensure you're using `@pytest.mark.asyncio` decorator for async tests.

### Mock not working
Check that you're mocking at the right level and using `AsyncMock` for async functions.

## Future Enhancements

- [ ] Add integration tests for full pipeline execution
- [ ] Add performance benchmarks
- [ ] Add mutation testing for better coverage quality
- [ ] Add property-based testing with Hypothesis

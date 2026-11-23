"""Repository-wide test execution policy."""

import asyncio

import pytest

pytest_plugins = ['tests.utils.required_suites', 'tests.utils.plugin_installations']


@pytest.fixture(scope='session')
def event_loop_policy():
    """Start pytest-asyncio without an implicit loop for other runners to orphan."""
    previous = asyncio.get_event_loop_policy()
    policy = asyncio.DefaultEventLoopPolicy()
    policy.set_event_loop(None)
    asyncio.set_event_loop_policy(policy)
    try:
        yield policy
    finally:
        asyncio.set_event_loop_policy(previous)

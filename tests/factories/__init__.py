"""
Shared test factories for LangBot tests.

Provides reusable factories for:
- Fake application (app.py)
- Messages and queries (message.py)
- Fake providers (provider.py)
- Fake platforms (platform.py)

Usage:
    from tests.factories import FakeApp, text_query, FakeProvider

    app = FakeApp()
    query = text_query("hello")
    provider = FakeProvider.returns("response")
"""

from tests.factories.app import FakeApp, fake_app
from tests.factories.message import (
    text_chain,
    group_text_chain,
    mention_chain,
    image_chain,
    text_query,
    group_text_query,
    private_text_query,
    command_query,
    mention_query,
    empty_query,
    image_query,
    file_query,
    unsupported_query,
    voice_query,
    at_all_query,
    query_with_session,
    query_with_config,
    friend_message_event,
    group_message_event,
    mock_adapter,
)
from tests.factories.provider import (
    FakeProvider,
    fake_provider,
    fake_provider_pong,
    fake_provider_timeout,
    fake_provider_auth_error,
    fake_provider_rate_limit,
    fake_provider_malformed,
    fake_model,
)
from tests.factories.platform import (
    FakePlatform,
    fake_platform,
    fake_platform_with_streaming,
    fake_platform_with_failure,
    mock_platform_adapter,
)

__all__ = [
    # App
    "FakeApp",
    "fake_app",
    # Message chains
    "text_chain",
    "group_text_chain",
    "mention_chain",
    "image_chain",
    # Message events
    "friend_message_event",
    "group_message_event",
    # Mock adapters
    "mock_adapter",
    # Queries
    "text_query",
    "group_text_query",
    "private_text_query",
    "command_query",
    "mention_query",
    "empty_query",
    "image_query",
    "file_query",
    "unsupported_query",
    "voice_query",
    "at_all_query",
    "query_with_session",
    "query_with_config",
    # Provider
    "FakeProvider",
    "fake_provider",
    "fake_provider_pong",
    "fake_provider_timeout",
    "fake_provider_auth_error",
    "fake_provider_rate_limit",
    "fake_provider_malformed",
    "fake_model",
    # Platform
    "FakePlatform",
    "fake_platform",
    "fake_platform_with_streaming",
    "fake_platform_with_failure",
    "mock_platform_adapter",
]
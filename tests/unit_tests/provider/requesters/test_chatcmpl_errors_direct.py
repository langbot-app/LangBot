"""Tests for requester error handling - direct import version.

Tests error handling branches by importing real packages and mocking
only the necessary dependencies.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
import openai  # Import real openai package

from langbot.pkg.provider.modelmgr.errors import RequesterError


class TestInvokeLLMErrorHandling:
    """Tests for invoke_llm error handling branches."""

    @pytest.fixture
    def mock_app(self):
        """Create mock Application."""
        app = MagicMock()
        app.tool_mgr = MagicMock()
        app.tool_mgr.generate_tools_for_openai = AsyncMock(return_value=[])
        return app

    @pytest.fixture
    def mock_model(self):
        """Create mock RuntimeLLMModel."""
        model = MagicMock()
        model.model_entity = MagicMock()
        model.model_entity.name = 'gpt-4'
        model.provider = MagicMock()
        model.provider.token_mgr = MagicMock()
        model.provider.token_mgr.get_token = MagicMock(return_value='test-key')
        return model

    @pytest.fixture
    def mock_message(self):
        """Create mock provider message."""
        msg = MagicMock()
        msg.dict = MagicMock(return_value={'role': 'user', 'content': 'test'})
        return msg

    @pytest.fixture
    def requester_with_mocked_client(self, mock_app):
        """Create requester with mocked OpenAI client."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        req = OpenAIChatCompletions(mock_app, {
            'base_url': 'https://api.openai.com/v1',
            'timeout': 120,
        })

        # Replace client with mock
        req.client = MagicMock()
        req.client.chat = MagicMock()
        req.client.chat.completions = MagicMock()
        req.client.chat.completions.create = AsyncMock()

        return req

    @pytest.mark.asyncio
    async def test_timeout_error(self, requester_with_mocked_client, mock_model, mock_message):
        """TimeoutError is wrapped as RequesterError."""
        requester_with_mocked_client.client.chat.completions.create = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_llm(
                query=None,
                model=mock_model,
                messages=[mock_message],
            )

        assert '超时' in str(exc.value)

    @pytest.mark.asyncio
    async def test_bad_request_context_length(self, requester_with_mocked_client, mock_model, mock_message):
        """BadRequestError with context_length_exceeded has special message."""
        error = openai.BadRequestError(
            message='context_length_exceeded: max 4096',
            response=MagicMock(status_code=400),
            body={}
        )
        requester_with_mocked_client.client.chat.completions.create = AsyncMock(
            side_effect=error
        )

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_llm(
                query=None,
                model=mock_model,
                messages=[mock_message],
            )

        assert '上文过长' in str(exc.value)

    @pytest.mark.asyncio
    async def test_authentication_error(self, requester_with_mocked_client, mock_model, mock_message):
        """AuthenticationError shows invalid api-key message."""
        error = openai.AuthenticationError(
            message='Invalid API key',
            response=MagicMock(status_code=401),
            body={}
        )
        requester_with_mocked_client.client.chat.completions.create = AsyncMock(
            side_effect=error
        )

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_llm(
                query=None,
                model=mock_model,
                messages=[mock_message],
            )

        assert 'api-key' in str(exc.value).lower() or '无效' in str(exc.value)

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, requester_with_mocked_client, mock_model, mock_message):
        """RateLimitError shows rate limit message."""
        error = openai.RateLimitError(
            message='Rate limit exceeded',
            response=MagicMock(status_code=429),
            body={}
        )
        requester_with_mocked_client.client.chat.completions.create = AsyncMock(
            side_effect=error
        )

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_llm(
                query=None,
                model=mock_model,
                messages=[mock_message],
            )

        assert '频繁' in str(exc.value) or '余额' in str(exc.value)


class TestInvokeEmbeddingErrorHandling:
    """Tests for invoke_embedding error handling."""

    @pytest.fixture
    def mock_app(self):
        return MagicMock()

    @pytest.fixture
    def mock_embedding_model(self):
        model = MagicMock()
        model.model_entity = MagicMock()
        model.model_entity.name = 'text-embedding-ada-002'
        model.model_entity.extra_args = {}
        model.provider = MagicMock()
        model.provider.token_mgr = MagicMock()
        model.provider.token_mgr.get_token = MagicMock(return_value='test-key')
        return model

    @pytest.fixture
    def requester_with_mocked_client(self, mock_app):
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        req = OpenAIChatCompletions(mock_app, {})
        req.client = MagicMock()
        req.client.embeddings = MagicMock()
        req.client.embeddings.create = AsyncMock()

        return req

    @pytest.mark.asyncio
    async def test_embedding_timeout_error(self, requester_with_mocked_client, mock_embedding_model):
        """TimeoutError in embedding request."""
        requester_with_mocked_client.client.embeddings.create = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_embedding(
                model=mock_embedding_model,
                input_text=['test'],
            )

        assert '超时' in str(exc.value)

    @pytest.mark.asyncio
    async def test_embedding_bad_request_error(self, requester_with_mocked_client, mock_embedding_model):
        """BadRequestError in embedding request."""
        error = openai.BadRequestError(
            message='Invalid model',
            response=MagicMock(status_code=400),
            body={}
        )
        requester_with_mocked_client.client.embeddings.create = AsyncMock(
            side_effect=error
        )

        with pytest.raises(RequesterError) as exc:
            await requester_with_mocked_client.invoke_embedding(
                model=mock_embedding_model,
                input_text=['test'],
            )

        assert '参数' in str(exc.value)


class TestRequesterErrorClass:
    """Tests for RequesterError."""

    def test_error_message_prefix(self):
        """RequesterError has '模型请求失败' prefix."""
        from langbot.pkg.provider.modelmgr.errors import RequesterError

        error = RequesterError('test error')
        assert '模型请求失败' in str(error)

    def test_error_is_exception(self):
        """RequesterError inherits Exception."""
        from langbot.pkg.provider.modelmgr.errors import RequesterError

        error = RequesterError('test')
        assert isinstance(error, Exception)


class TestDefaultConfig:
    """Tests for requester default config."""

    def test_default_config(self):
        """Check default_config values."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        assert OpenAIChatCompletions.default_config['base_url'] == 'https://api.openai.com/v1'
        assert OpenAIChatCompletions.default_config['timeout'] == 120

    def test_config_override(self):
        """Config overrides defaults."""
        from langbot.pkg.provider.modelmgr.requesters.chatcmpl import OpenAIChatCompletions

        req = OpenAIChatCompletions(MagicMock(), {
            'base_url': 'https://custom.com/v1',
            'timeout': 60,
        })

        assert req.requester_cfg['base_url'] == 'https://custom.com/v1'
        assert req.requester_cfg['timeout'] == 60

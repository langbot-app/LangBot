"""
Minimal fake flow smoke tests for LangBot.

These tests verify basic component interactions using fake providers and platforms.
Not a full pipeline integration test - tests individual factory components.

For full pipeline tests, see tests/integration/ (planned).
"""

from __future__ import annotations

import pytest

from tests.factories import (
    FakeApp,
    FakeProvider,
    FakePlatform,
    text_query,
    fake_provider_pong,
    fake_model,
    mock_platform_adapter,
)


class TestFakeMessageFlow:
    """Smoke tests for fake message flow through pipeline."""

    @pytest.mark.asyncio
    async def test_fake_app_creation(self):
        """Test FakeApp can be created with all dependencies."""
        app = FakeApp()

        assert app.logger is not None
        assert app.sess_mgr is not None
        assert app.model_mgr is not None
        assert app.tool_mgr is not None
        assert app.persistence_mgr is not None
        assert app.query_pool is not None
        assert app.instance_config is not None

        # Verify default config
        assert app.instance_config.data["command"]["prefix"] == ["/", "!"]
        assert app.instance_config.data["command"]["enable"] is True

    @pytest.mark.asyncio
    async def test_fake_provider_returns_text(self):
        """Test FakeProvider returns configured response."""
        provider = FakeProvider(default_response="test response")

        # Create mock model with provider
        model = fake_model(provider=provider)

        # Create a simple query
        query = text_query("hello")

        # Simulate invoke
        result = await provider.invoke_llm(
            query=query,
            model=model,
            messages=[],
            funcs=[],
            extra_args={},
        )

        assert result is not None
        assert result.role == "assistant"
        assert result.content == "test response"

    @pytest.mark.asyncio
    async def test_fake_provider_pong(self):
        """Test FakeProvider returns LANGBOT_FAKE_PONG marker."""
        provider = fake_provider_pong()
        model = fake_model(provider=provider)
        query = text_query("ping")

        result = await provider.invoke_llm(
            query=query,
            model=model,
            messages=[],
            funcs=[],
            extra_args={},
        )

        assert result.content == FakeProvider.PONG_RESPONSE

    @pytest.mark.asyncio
    async def test_fake_provider_streaming(self):
        """Test FakeProvider streaming response."""
        provider = FakeProvider().returns_streaming(["Hello", " World"])
        model = fake_model(provider=provider)
        query = text_query("hello")

        chunks = []
        # invoke_llm_stream returns an async generator, don't await it
        async for chunk in provider.invoke_llm_stream(
            query=query,
            model=model,
            messages=[],
            funcs=[],
            extra_args={},
        ):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " World"
        assert chunks[1].is_final is True

    @pytest.mark.asyncio
    async def test_fake_provider_timeout(self):
        """Test FakeProvider simulates timeout error."""
        provider = FakeProvider().timeout()
        model = fake_model(provider=provider)
        query = text_query("hello")

        with pytest.raises(TimeoutError, match="Provider timeout"):
            await provider.invoke_llm(
                query=query,
                model=model,
                messages=[],
                funcs=[],
                extra_args={},
            )

    @pytest.mark.asyncio
    async def test_fake_provider_rate_limit(self):
        """Test FakeProvider simulates rate limit error."""
        provider = FakeProvider().rate_limit()
        model = fake_model(provider=provider)
        query = text_query("hello")

        with pytest.raises(Exception, match="Rate limit exceeded"):
            await provider.invoke_llm(
                query=query,
                model=model,
                messages=[],
                funcs=[],
                extra_args={},
            )

    @pytest.mark.asyncio
    async def test_fake_provider_captures_requests(self):
        """Test FakeProvider captures request arguments."""
        provider = FakeProvider()
        model = fake_model(name="gpt-4", provider=provider)
        query = text_query("hello")

        await provider.invoke_llm(
            query=query,
            model=model,
            messages=[{"role": "user", "content": "hello"}],
            funcs=[{"name": "test_func"}],
            extra_args={"temperature": 0.7},
        )

        captured = provider.get_captured_requests()
        assert len(captured) == 1
        assert captured[0]["model"] == "gpt-4"
        assert captured[0]["messages"] == [{"role": "user", "content": "hello"}]
        assert captured[0]["funcs"] == [{"name": "test_func"}]
        assert captured[0]["extra_args"] == {"temperature": 0.7}

    @pytest.mark.asyncio
    async def test_fake_platform_capture_outbound(self):
        """Test FakePlatform captures outbound messages."""
        platform = FakePlatform(bot_account_id="test-bot")
        query = text_query("hello")

        # Simulate sending reply
        from tests.factories.message import text_chain

        reply_chain = text_chain("response text")
        event = query.message_event

        await platform.reply_message(event, reply_chain, quote_origin=False)

        # Verify captured
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1
        assert outbound[0]["type"] == "reply"
        assert outbound[0]["message"] == reply_chain

    @pytest.mark.asyncio
    async def test_fake_platform_friend_message(self):
        """Test FakePlatform creates friend message events."""
        platform = FakePlatform(bot_account_id="test-bot")

        event = platform.create_friend_message(
            text="hello bot",
            sender_id=12345,
            nickname="TestUser",
        )

        assert event.type == "FriendMessage"
        assert event.sender.id == 12345
        assert event.sender.nickname == "TestUser"
        assert str(event.message_chain) == "hello bot"

    @pytest.mark.asyncio
    async def test_fake_platform_group_message_with_mention(self):
        """Test FakePlatform creates group message with @mention."""
        platform = FakePlatform(bot_account_id="test-bot")

        event = platform.create_group_message(
            text="hello everyone",
            sender_id=12345,
            group_id=99999,
            mention_bot=True,
        )

        assert event.type == "GroupMessage"
        assert event.sender.id == 12345
        assert event.group.id == 99999

        # Check message chain has @mention
        chain = event.message_chain
        assert len(chain) >= 2  # At + Plain

    @pytest.mark.asyncio
    async def test_query_factories_basic(self):
        """Test basic query factory functions."""
        # Text query
        q1 = text_query("hello world")
        assert q1.launcher_type.value == "person"
        assert str(q1.message_chain) == "hello world"

        # Group query
        from tests.factories import group_text_query
        q2 = group_text_query("hello group", group_id=88888)
        assert q2.launcher_type.value == "group"
        assert q2.launcher_id == 88888

        # Command query
        from tests.factories import command_query
        q3 = command_query("help", prefix="/")
        assert str(q3.message_chain) == "/help"

        # Mention query
        from tests.factories import mention_query
        q4 = mention_query("hi", target="test-bot", group_id=77777)
        assert q4.launcher_type.value == "group"

    @pytest.mark.asyncio
    async def test_fake_platform_send_failure(self):
        """Test FakePlatform simulates send failure."""
        platform = FakePlatform().send_failure()
        query = text_query("hello")

        from tests.factories.message import text_chain

        with pytest.raises(Exception, match="Platform send failure"):
            await platform.reply_message(
                query.message_event,
                text_chain("response"),
            )

    @pytest.mark.asyncio
    async def test_mock_platform_adapter(self):
        """Test mock_platform_adapter helper."""
        platform = FakePlatform(bot_account_id="bot-123")
        adapter = mock_platform_adapter(platform)

        assert adapter.bot_account_id == "bot-123"
        assert adapter._fake_platform is platform

        # Test reply_message is wired
        from tests.factories.message import text_chain

        query = text_query("test")
        await adapter.reply_message(query.message_event, text_chain("response"))

        # Verify platform captured it
        assert len(platform.get_outbound_messages()) == 1


class TestMessageFlowIntegration:
    """Minimal fake flow integration tests.

    These tests verify component interactions but do NOT run full LangBot pipeline.
    For real pipeline tests, integration tests are needed (planned).
    """

    @pytest.mark.asyncio
    async def test_minimal_message_flow(self):
        """Minimal fake flow test: fake query -> fake provider -> fake platform.

        This test verifies:
        1. Fake text query is created
        2. Fake provider returns LANGBOT_FAKE_PONG
        3. Fake platform captures outbound response
        4. No unexpected exception

        Note: This does NOT run actual LangBot pipeline stages.
        """
        # Setup
        platform = FakePlatform(bot_account_id="test-bot")
        provider = fake_provider_pong()
        model = fake_model(provider=provider)

        # Create inbound message
        query = text_query("ping")

        # Simulate provider processing
        response = await provider.invoke_llm(
            query=query,
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            funcs=[],
            extra_args={},
        )

        # Verify provider returned pong
        assert response.content == FakeProvider.PONG_RESPONSE

        # Simulate platform sending response
        from tests.factories.message import text_chain

        reply_chain = text_chain(response.content)
        await platform.reply_message(query.message_event, reply_chain)

        # Verify platform captured outbound
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1
        assert outbound[0]["type"] == "reply"
        assert str(outbound[0]["message"]) == FakeProvider.PONG_RESPONSE

    @pytest.mark.asyncio
    async def test_streaming_message_flow(self):
        """Smoke test: streaming message flow."""
        platform = FakePlatform().supports_streaming()
        provider = FakeProvider().returns_streaming(["Hello", " there"])
        model = fake_model(provider=provider)
        query = text_query("hi")

        chunks = []
        async for chunk in provider.invoke_llm_stream(
            query=query,
            model=model,
            messages=[],
            funcs=[],
            extra_args={},
        ):
            chunks.append(chunk)

        # Verify streaming worked
        assert len(chunks) == 2
        full_content = "".join(c.content for c in chunks)
        assert full_content == "Hello there"

        # Verify platform supports streaming
        assert await platform.is_stream_output_supported() is True
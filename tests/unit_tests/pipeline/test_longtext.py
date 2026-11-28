"""
Unit tests for LongTextProcessStage (longtext) pipeline stage.

Tests cover:
- Strategy selection (none/image/forward)
- Threshold boundary handling
- Plain/non-Plain component handling
- Strategy initialization and process
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module
from types import SimpleNamespace

from tests.factories import (
    FakeApp,
    text_query,
)

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from .outer_stage_harness import bind_policy


def get_longtext_module():
    """Lazy import to avoid circular import issues."""
    # Import pipelinemgr first to trigger stage registration
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.longtext.longtext')


def get_strategy_module():
    """Lazy import for strategy base."""
    return import_module('langbot.pkg.pipeline.longtext.strategy')


def get_entities_module():
    """Lazy import for pipeline entities."""
    return import_module('langbot.pkg.pipeline.entities')


def make_longtext_config(strategy: str = 'none', threshold: int = 1000):
    """Create a pipeline config for long text processing."""
    return {
        'output': {
            'long-text-processing': {
                'strategy': strategy,
                'threshold': threshold,
                'font-path': '/nonexistent/font.ttf',  # For image strategy
            }
        }
    }


class TestLongTextStrategySelection:
    """The long-text strategy a message policy compiles from its settings."""

    @pytest.mark.asyncio
    async def test_none_strategy(self):
        """strategy='none' compiles to no strategy at all."""
        policy = await bind_policy(FakeApp(), text_query('hello'), make_longtext_config(strategy='none'))

        assert policy.long_text_strategy is None

    @pytest.mark.asyncio
    async def test_forward_strategy(self):
        """strategy='forward' compiles to ForwardComponentStrategy."""
        forward = import_module('langbot.pkg.pipeline.longtext.strategies.forward')

        policy = await bind_policy(FakeApp(), text_query('hello'), make_longtext_config(strategy='forward'))

        assert isinstance(policy.long_text_strategy, forward.ForwardComponentStrategy)

    @pytest.mark.asyncio
    async def test_unknown_strategy_raises(self):
        """A strategy that is not registered cannot be compiled."""
        get_longtext_module()
        strategy = get_strategy_module()

        # Save original preregistered_strategies
        original_strategies = strategy.preregistered_strategies.copy()

        try:
            # Clear registered strategies to simulate unknown
            strategy.preregistered_strategies = []

            with pytest.raises(ValueError, match='Long message processing strategy not found'):
                await bind_policy(FakeApp(), text_query('hello'), make_longtext_config(strategy='unknown'))
        finally:
            # Restore original strategies
            strategy.preregistered_strategies = original_strategies


class TestLongTextProcessStageProcess:
    """Tests for LongTextProcessStage process behavior."""

    @pytest.mark.asyncio
    async def test_none_strategy_continues(self):
        """strategy='none' should always continue."""
        longtext = get_longtext_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        pipeline_config = make_longtext_config(strategy='none')

        await stage.initialize(pipeline_config)

        query = text_query('hello')
        query.pipeline_config = pipeline_config
        await bind_policy(app, query)
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='very long response')])]

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query is not None

    @pytest.mark.asyncio
    async def test_short_text_continues_without_transform(self):
        """Text shorter than threshold should not be transformed."""
        longtext = get_longtext_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        # High threshold so text won't trigger transform
        pipeline_config = make_longtext_config(strategy='forward', threshold=10000)

        await stage.initialize(pipeline_config)

        query = text_query('hello')
        query.pipeline_config = pipeline_config
        await bind_policy(app, query)
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='short response')])]

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        assert len(result.new_query.resp_message_chain) == 1
        components = list(result.new_query.resp_message_chain[0])
        assert len(components) == 1
        assert isinstance(components[0], platform_message.Plain)
        assert components[0].text == 'short response'

    @pytest.mark.asyncio
    async def test_non_plain_component_skips(self):
        """resp_message_chain with non-Plain components should skip processing."""
        longtext = get_longtext_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        pipeline_config = make_longtext_config(strategy='forward', threshold=10)  # Low threshold

        await stage.initialize(pipeline_config)

        query = text_query('hello')
        query.pipeline_config = pipeline_config
        await bind_policy(app, query)
        # Non-Plain component (Image)
        query.resp_message_chain = [
            platform_message.MessageChain(
                [platform_message.Plain(text='short'), platform_message.Image(url='https://example.com/img.png')]
            )
        ]

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        components = list(result.new_query.resp_message_chain[0])
        assert [type(component) for component in components] == [
            platform_message.Plain,
            platform_message.Image,
        ]
        assert components[0].text == 'short'
        assert components[1].url == 'https://example.com/img.png'

    @pytest.mark.asyncio
    async def test_empty_resp_message_chain(self):
        """Empty resp_message_chain should be handled gracefully."""
        longtext = get_longtext_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        pipeline_config = make_longtext_config(strategy='forward')

        await stage.initialize(pipeline_config)

        query = text_query('hello')
        query.pipeline_config = pipeline_config
        await bind_policy(app, query)
        query.resp_message_chain = []

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query is query

    @pytest.mark.asyncio
    async def test_empty_response_message_chain_does_not_call_strategy(self):
        """Empty response chains should be a no-op for long text processing."""
        longtext = get_longtext_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        query = text_query('hello')
        policy = await bind_policy(app, query, make_longtext_config(strategy='forward', threshold=1))
        policy.long_text_strategy = AsyncMock()
        query.resp_message_chain = []

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query is query
        policy.long_text_strategy.process.assert_not_called()


class TestForwardStrategy:
    """Tests for ForwardComponentStrategy."""

    @pytest.mark.asyncio
    async def test_forward_strategy_processes(self):
        """ForwardComponentStrategy should create Forward component."""
        longtext = get_longtext_module()
        get_strategy_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        # Low threshold to trigger
        pipeline_config = make_longtext_config(strategy='forward', threshold=10)

        await stage.initialize(pipeline_config)

        query = text_query('hello')
        query.pipeline_config = pipeline_config
        await bind_policy(app, query)
        # Create a mock adapter with bot_account_id
        mock_adapter = Mock()
        mock_adapter.bot_account_id = '12345'
        query.adapter = mock_adapter

        # Long text exceeding threshold
        long_text = 'This is a very long response that exceeds the threshold'
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text=long_text)])]

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        components = list(result.new_query.resp_message_chain[0])
        assert len(components) == 1
        assert isinstance(components[0], platform_message.Forward)

    @pytest.mark.asyncio
    async def test_forward_strategy_direct_process(self):
        """Test ForwardComponentStrategy process method directly."""
        strategy = get_strategy_module()

        app = FakeApp()

        # Get ForwardComponentStrategy from preregistered
        for strat_cls in strategy.preregistered_strategies:
            if strat_cls.name == 'forward':
                strat = strat_cls(app)
                break
        else:
            pytest.skip('ForwardComponentStrategy not registered')

        await strat.initialize()

        query = text_query('hello')
        query.pipeline_config = make_longtext_config()
        mock_adapter = Mock()
        mock_adapter.bot_account_id = '12345'
        query.adapter = mock_adapter

        components = await strat.process('test message', query)

        assert len(components) == 1
        assert isinstance(components[0], platform_message.Forward)


class TestLongTextThreshold:
    """Tests for threshold boundary handling."""

    @pytest.mark.asyncio
    async def test_below_threshold_not_processed(self):
        """Text below threshold should not be transformed."""
        longtext = get_longtext_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = longtext.LongTextProcessStage(app)

        threshold = 100
        pipeline_config = make_longtext_config(strategy='forward', threshold=threshold)

        await stage.initialize(pipeline_config)

        query = text_query('hello')
        query.pipeline_config = pipeline_config
        await bind_policy(app, query)

        # Text below threshold
        short_text = 'x' * (threshold - 1)
        query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text=short_text)])]

        result = await stage.process(query, 'LongTextProcessStage')

        assert result.result_type == entities.ResultType.CONTINUE
        components = list(result.new_query.resp_message_chain[0])
        assert len(components) == 1
        assert isinstance(components[0], platform_message.Plain)
        assert components[0].text == short_text


class TestLongTextProcessStageImageStrategy:
    """Tests for image strategy handling (requires PIL/font)."""

    @pytest.mark.asyncio
    async def test_image_strategy_missing_font_fallback(self, monkeypatch):
        """Missing font should fallback to forward strategy."""
        get_longtext_module()
        forward = import_module('langbot.pkg.pipeline.longtext.strategies.forward')
        policy_runtime = import_module('langbot.pkg.message_policy.runtime')
        monkeypatch.setattr(
            policy_runtime, 'os', SimpleNamespace(name='posix', path=SimpleNamespace(exists=lambda _: False))
        )

        query = text_query('hello')

        # On non-Windows without font, should fallback to forward
        policy = await bind_policy(FakeApp(), query, make_longtext_config(strategy='image'))

        assert query.pipeline_config['output']['long-text-processing']['strategy'] == 'forward'
        assert isinstance(policy.long_text_strategy, forward.ForwardComponentStrategy)

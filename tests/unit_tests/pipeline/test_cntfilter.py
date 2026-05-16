"""
Unit tests for ContentFilterStage (cntfilter) pipeline stage.

Tests cover:
- Pre-filter behavior (income message filtering)
- Post-filter behavior (output message filtering)
- Content ignore rules (prefix/regexp)
- Pass/Block/Masked result handling
- CONTINUE/INTERRUPT flow control
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock
from importlib import import_module

from tests.factories import (
    FakeApp,
    text_query,
    image_query,
)

import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.platform.message as platform_message


def get_cntfilter_module():
    """Lazy import to avoid circular import issues."""
    # Import pipelinemgr first to trigger stage registration
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.cntfilter.cntfilter')


def get_filter_module():
    """Lazy import for filter base."""
    return import_module('langbot.pkg.pipeline.cntfilter.filter')


def get_entities_module():
    """Lazy import for pipeline entities."""
    return import_module('langbot.pkg.pipeline.entities')


def get_filter_entities_module():
    """Lazy import for filter entities."""
    return import_module('langbot.pkg.pipeline.cntfilter.entities')


def make_pipeline_config(**overrides):
    """Create a pipeline config with defaults for content filter tests."""
    base_config = {
        'safety': {
            'content-filter': {
                'check-sensitive-words': False,
                'scope': 'both',
            }
        },
        'trigger': {
            'ignore-rules': {
                'prefix': [],
                'regexp': [],
            }
        },
    }
    # Deep merge for nested dicts
    for key, value in overrides.items():
        if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key in base_config[key] and isinstance(base_config[key][sub_key], dict) and isinstance(sub_value, dict):
                    base_config[key][sub_key].update(sub_value)
                else:
                    base_config[key][sub_key] = sub_value
        else:
            base_config[key] = value
    return base_config


class TestContentFilterStageInit:
    """Tests for ContentFilterStage initialization."""

    @pytest.mark.asyncio
    async def test_initialize_basic_filters(self):
        """Initialize should load required filters."""
        cntfilter = get_cntfilter_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        assert [filter_impl.name for filter_impl in stage.filter_chain] == ['content-ignore']

    @pytest.mark.asyncio
    async def test_initialize_with_sensitive_words(self):
        """Initialize with sensitive words should load ban-word-filter."""
        cntfilter = get_cntfilter_module()

        app = FakeApp()
        # Mock sensitive_meta for ban-word-filter
        app.sensitive_meta = Mock()
        app.sensitive_meta.data = {
            'words': [],
            'mask': '*',
            'mask_word': '',
        }

        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            safety={
                'content-filter': {
                    'check-sensitive-words': True,
                }
            }
        )

        await stage.initialize(pipeline_config)

        assert {filter_impl.name for filter_impl in stage.filter_chain} == {
            'ban-word-filter',
            'content-ignore',
        }


class TestPreContentFilter:
    """Tests for PreContentFilterStage (income message filtering)."""

    @pytest.mark.asyncio
    async def test_normal_text_continues(self):
        """Normal text message should continue pipeline."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello world")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        assert result.result_type == entities.ResultType.CONTINUE
        assert result.new_query is not None

    @pytest.mark.asyncio
    async def test_empty_text_continues(self):
        """Empty text message should continue pipeline."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        # Empty message chain
        query = text_query("")
        query.message_chain = platform_message.MessageChain([])
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Empty messages should continue
        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_whitespace_only_continues(self):
        """Whitespace-only message should continue pipeline."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("   ")  # Only whitespace
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Whitespace-only should continue (stripped becomes empty)
        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_non_text_component_continues(self):
        """Message with non-text components should continue (skip filter)."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        # Image message (non-text)
        query = image_query()
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Non-text messages should continue (skip filter)
        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_output_scope_skip_pre_filter(self):
        """scope=output-msg should skip pre-filter."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            safety={
                'content-filter': {
                    'scope': 'output-msg',  # Only check output
                }
            }
        )

        await stage.initialize(pipeline_config)

        query = text_query("hello world")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Should continue without filtering
        assert result.result_type == entities.ResultType.CONTINUE


class TestContentIgnoreFilter:
    """Tests for content-ignore filter rules."""

    @pytest.mark.asyncio
    async def test_prefix_rule_blocks(self):
        """Message matching prefix ignore rule should be blocked."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            trigger={
                'ignore-rules': {
                    'prefix': ['/help', '/ping'],
                    'regexp': [],
                }
            }
        )

        await stage.initialize(pipeline_config)

        query = text_query("/help me")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Should be interrupted due to prefix rule
        assert result.result_type == entities.ResultType.INTERRUPT

    @pytest.mark.asyncio
    async def test_regexp_rule_blocks(self):
        """Message matching regexp ignore rule should be blocked."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            trigger={
                'ignore-rules': {
                    'prefix': [],
                    'regexp': ['^http://.*', r'\d{10}'],
                }
            }
        )

        await stage.initialize(pipeline_config)

        query = text_query("http://example.com")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Should be interrupted due to regexp rule
        assert result.result_type == entities.ResultType.INTERRUPT

    @pytest.mark.asyncio
    async def test_no_rule_match_continues(self):
        """Message not matching any rule should continue."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            trigger={
                'ignore-rules': {
                    'prefix': ['/help', '/ping'],
                    'regexp': ['^http://.*'],
                }
            }
        )

        await stage.initialize(pipeline_config)

        query = text_query("normal message")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Should continue (no rule match)
        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_empty_rules_continues(self):
        """Empty ignore rules should not block any message."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("/help me")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        # Should continue (empty rules)
        assert result.result_type == entities.ResultType.CONTINUE


class TestPostContentFilter:
    """Tests for PostContentFilterStage (output message filtering)."""

    @pytest.mark.asyncio
    async def test_normal_response_continues(self):
        """Normal response message should continue pipeline."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        # Add a response message
        query.resp_messages = [
            provider_message.Message(role='assistant', content='Hello back!')
        ]

        result = await stage.process(query, 'PostContentFilterStage')

        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_income_scope_skip_post_filter(self):
        """scope=income-msg should skip post-filter."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            safety={
                'content-filter': {
                    'scope': 'income-msg',  # Only check income
                }
            }
        )

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_messages = [
            provider_message.Message(role='assistant', content='Response')
        ]

        result = await stage.process(query, 'PostContentFilterStage')

        # Should continue without filtering
        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_non_string_content_continues(self):
        """Non-string content should continue (skip filter)."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        # Non-string content - use model_construct to bypass validation
        # The actual content type could be a list of ContentElement objects
        non_string_msg = provider_message.Message.model_construct(
            role='assistant',
            content=[Mock()],  # Mock content element
        )
        query.resp_messages = [non_string_msg]

        result = await stage.process(query, 'PostContentFilterStage')

        # Should continue (skip filter for non-string)
        assert result.result_type == entities.ResultType.CONTINUE

    @pytest.mark.asyncio
    async def test_empty_response_continues(self):
        """Empty response should continue pipeline."""
        cntfilter = get_cntfilter_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.resp_messages = [
            provider_message.Message(role='assistant', content='')
        ]

        result = await stage.process(query, 'PostContentFilterStage')

        assert result.result_type == entities.ResultType.CONTINUE


class TestContentFilterStageInvalidName:
    """Tests for invalid stage_inst_name handling."""

    @pytest.mark.asyncio
    async def test_unknown_stage_name_raises(self):
        """Unknown stage_inst_name should raise ValueError."""
        cntfilter = get_cntfilter_module()

        app = FakeApp()
        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config

        with pytest.raises(ValueError, match='未知的 stage_inst_name'):
            await stage.process(query, 'UnknownStage')


class TestContentIgnoreFilterDirect:
    """Direct tests for ContentIgnore filter."""

    @pytest.mark.asyncio
    async def test_content_ignore_pass(self):
        """ContentIgnore should PASS for non-matching messages."""
        cntfilter = get_cntfilter_module()

        app = FakeApp()

        stage = cntfilter.ContentFilterStage(app)

        pipeline_config = make_pipeline_config(
            trigger={
                'ignore-rules': {
                    'prefix': ['/test'],
                    'regexp': [],
                }
            }
        )

        await stage.initialize(pipeline_config)

        query = text_query("normal message without prefix")
        query.pipeline_config = pipeline_config

        result = await stage.process(query, 'PreContentFilterStage')

        assert result.result_type == cntfilter.entities.ResultType.CONTINUE

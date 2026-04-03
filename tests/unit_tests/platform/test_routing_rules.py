"""
RuntimeBot.resolve_pipeline_uuid and _match_operator unit tests
"""

import pytest
from unittest.mock import Mock


class TestMatchOperator:
    """Test the _match_operator static method."""

    @staticmethod
    def _get_class():
        from langbot.pkg.platform.botmgr import RuntimeBot

        return RuntimeBot

    def test_eq(self):
        cls = self._get_class()
        assert cls._match_operator('hello', 'eq', 'hello') is True
        assert cls._match_operator('hello', 'eq', 'world') is False

    def test_neq(self):
        cls = self._get_class()
        assert cls._match_operator('hello', 'neq', 'world') is True
        assert cls._match_operator('hello', 'neq', 'hello') is False

    def test_contains(self):
        cls = self._get_class()
        assert cls._match_operator('hello world', 'contains', 'world') is True
        assert cls._match_operator('hello world', 'contains', 'xyz') is False

    def test_not_contains(self):
        cls = self._get_class()
        assert cls._match_operator('hello world', 'not_contains', 'xyz') is True
        assert cls._match_operator('hello world', 'not_contains', 'world') is False

    def test_starts_with(self):
        cls = self._get_class()
        assert cls._match_operator('hello world', 'starts_with', 'hello') is True
        assert cls._match_operator('hello world', 'starts_with', 'world') is False

    def test_regex(self):
        cls = self._get_class()
        assert cls._match_operator('hello123', 'regex', r'\d+') is True
        assert cls._match_operator('hello', 'regex', r'\d+') is False

    def test_regex_invalid_pattern(self):
        cls = self._get_class()
        assert cls._match_operator('hello', 'regex', r'[invalid') is False

    def test_unknown_operator(self):
        cls = self._get_class()
        assert cls._match_operator('hello', 'unknown_op', 'hello') is False


class TestResolvePipelineUuid:
    """Test the resolve_pipeline_uuid method."""

    @staticmethod
    def _make_bot(default_pipeline: str, rules: list):
        from langbot.pkg.platform.botmgr import RuntimeBot

        bot_entity = Mock()
        bot_entity.use_pipeline_uuid = default_pipeline
        bot_entity.pipeline_routing_rules = rules

        bot = object.__new__(RuntimeBot)
        bot.bot_entity = bot_entity
        return bot

    def test_no_rules_returns_default(self):
        bot = self._make_bot('default-uuid', [])
        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_none_rules_returns_default(self):
        bot = self._make_bot('default-uuid', None)
        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_launcher_type_match(self):
        rules = [
            {
                'type': 'launcher_type',
                'operator': 'eq',
                'value': 'group',
                'pipeline_uuid': 'group-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('group', '123', 'hi')
        assert uuid == 'group-pipeline'
        assert routed is True

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_launcher_id_match(self):
        rules = [
            {
                'type': 'launcher_id',
                'operator': 'eq',
                'value': '12345',
                'pipeline_uuid': 'vip-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '12345', 'hi')
        assert uuid == 'vip-pipeline'
        assert routed is True

        uuid, routed = bot.resolve_pipeline_uuid('person', '99999', 'hi')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_message_content_contains(self):
        rules = [
            {
                'type': 'message_content',
                'operator': 'contains',
                'value': '紧急',
                'pipeline_uuid': 'urgent-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', '这是紧急消息')
        assert uuid == 'urgent-pipeline'
        assert routed is True

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', '普通消息')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_message_content_regex(self):
        rules = [
            {
                'type': 'message_content',
                'operator': 'regex',
                'value': r'^/admin\b',
                'pipeline_uuid': 'admin-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', '/admin help')
        assert uuid == 'admin-pipeline'
        assert routed is True

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hello /admin')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_message_has_element_eq(self):
        rules = [
            {
                'type': 'message_has_element',
                'operator': 'eq',
                'value': 'Image',
                'pipeline_uuid': 'image-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi', ['Plain', 'Image'])
        assert uuid == 'image-pipeline'
        assert routed is True

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi', ['Plain'])
        assert uuid == 'default-uuid'
        assert routed is False

    def test_message_has_element_neq(self):
        rules = [
            {
                'type': 'message_has_element',
                'operator': 'neq',
                'value': 'Image',
                'pipeline_uuid': 'text-only-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi', ['Plain'])
        assert uuid == 'text-only-pipeline'
        assert routed is True

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi', ['Plain', 'Image'])
        assert uuid == 'default-uuid'
        assert routed is False

    def test_message_has_element_no_types_provided(self):
        """When element types are not provided, should not match."""
        rules = [
            {
                'type': 'message_has_element',
                'operator': 'eq',
                'value': 'Image',
                'pipeline_uuid': 'image-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi')
        assert uuid == 'default-uuid'
        assert routed is False

    def test_first_match_wins(self):
        rules = [
            {
                'type': 'launcher_type',
                'operator': 'eq',
                'value': 'group',
                'pipeline_uuid': 'first-pipeline',
            },
            {
                'type': 'launcher_type',
                'operator': 'eq',
                'value': 'group',
                'pipeline_uuid': 'second-pipeline',
            },
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('group', '123', 'hi')
        assert uuid == 'first-pipeline'
        assert routed is True

    def test_skip_invalid_rules(self):
        rules = [
            {'type': '', 'operator': 'eq', 'value': 'x', 'pipeline_uuid': 'p1'},
            {'type': 'launcher_type', 'operator': 'eq', 'value': 'person', 'pipeline_uuid': ''},
            {'type': 'launcher_type', 'operator': 'eq', 'value': 'person', 'pipeline_uuid': 'valid'},
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi')
        assert uuid == 'valid'
        assert routed is True

    def test_default_operator_is_eq(self):
        rules = [
            {
                'type': 'launcher_type',
                'value': 'person',
                'pipeline_uuid': 'person-pipeline',
            }
        ]
        bot = self._make_bot('default-uuid', rules)

        uuid, routed = bot.resolve_pipeline_uuid('person', '123', 'hi')
        assert uuid == 'person-pipeline'
        assert routed is True

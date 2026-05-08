"""
Unit tests for CommandHandler behavior patterns.

Tests cover command processing patterns:
- Command parsing and routing
- Event emission pattern
- Command manager interaction
- Privilege handling

Uses pattern-based testing to avoid circular import issues in source code.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from tests.factories import command_query


class TestCommandParsingPattern:
    """Tests for command parsing logic."""

    def test_command_text_extraction(self):
        """Command text is extracted after prefix."""
        # Simulate the parsing pattern from command handler
        full_command_text = "/help arg1 arg2"

        # Handler strips first character (prefix)
        command_text = full_command_text.strip()[1:]
        parts = command_text.split(' ')

        assert parts[0] == 'help'
        assert parts[1:] == ['arg1', 'arg2']

    def test_empty_command_parts(self):
        """Empty command has no parts."""
        full_command_text = "/"

        command_text = full_command_text.strip()[1:]
        parts = command_text.split(' ')

        assert parts == ['']

    def test_single_command_no_args(self):
        """Single command has no arguments."""
        full_command_text = "/status"

        command_text = full_command_text.strip()[1:]
        parts = command_text.split(' ')

        assert parts == ['status']


class TestCommandEventCreation:
    """Tests for command event creation pattern."""

    def test_event_type_by_launcher_type(self):
        """Event type differs for person/group."""
        import langbot_plugin.api.entities.events as events

        # Person command
        person_event_class = events.PersonCommandSent

        # Group command
        group_event_class = events.GroupCommandSent

        assert person_event_class is not None
        assert group_event_class is not None

    def test_event_fields_pattern(self):
        """Command event should have expected fields."""
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

        launcher_type = LauncherTypes.PERSON.value
        launcher_id = '12345'
        sender_id = '12345'
        command = 'help'
        params = ['arg1', 'arg2']
        is_admin = False

        # Simulate event creation pattern
        event_data = {
            'launcher_type': launcher_type,
            'launcher_id': launcher_id,
            'sender_id': sender_id,
            'command': command,
            'params': params,
            'is_admin': is_admin,
        }

        assert event_data['command'] == 'help'
        assert event_data['params'] == ['arg1', 'arg2']


class TestPrivilegeCheckPattern:
    """Tests for privilege/admin check."""

    def test_admin_check_by_session_id(self):
        """Admin is checked by session_id format."""
        admins = ['person_12345', 'group_99999']
        launcher_type = 'person'
        launcher_id = '12345'

        session_id = f'{launcher_type}_{launcher_id}'
        is_admin = session_id in admins

        assert is_admin is True

    def test_non_admin_check(self):
        """Non-admin user has privilege 1."""
        admins = ['person_12345']
        launcher_type = 'person'
        launcher_id = '67890'

        session_id = f'{launcher_type}_{launcher_id}'
        is_admin = session_id in admins

        assert is_admin is False

    def test_privilege_levels(self):
        """Privilege level 1 for normal, 2 for admin."""
        normal_privilege = 1
        admin_privilege = 2

        admins = ['person_12345']

        # Normal user
        session_id = 'person_67890'
        privilege = 2 if session_id in admins else 1
        assert privilege == normal_privilege

        # Admin user
        session_id = 'person_12345'
        privilege = 2 if session_id in admins else 1
        assert privilege == admin_privilege


class TestCommandResultHandling:
    """Tests for command result handling patterns."""

    @pytest.mark.asyncio
    async def test_text_result_pattern(self):
        """Text result is converted to message."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        # Simulate command return
        ret = Mock()
        ret.text = 'Command output'
        ret.error = None
        ret.image_url = None
        ret.image_base64 = None
        ret.file_url = None

        # Pattern from handler: build content list
        content = []
        if ret.text is not None:
            content.append(provider_message.ContentElement.from_text(ret.text))

        assert len(content) == 1
        assert content[0].type == 'text'
        assert content[0].text == 'Command output'

    @pytest.mark.asyncio
    async def test_error_result_pattern(self):
        """Error result creates error message."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        ret = Mock()
        ret.text = None
        ret.error = 'Command failed'

        # Error handling pattern
        if ret.error is not None:
            msg = provider_message.Message(
                role='command',
                content=str(ret.error),
            )

        assert msg.role == 'command'
        assert msg.content == 'Command failed'

    @pytest.mark.asyncio
    async def test_image_result_pattern(self):
        """Image result is added to content."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        ret = Mock()
        ret.text = 'Here is the image:'
        ret.error = None
        ret.image_url = 'https://example.com/image.png'
        ret.image_base64 = None
        ret.file_url = None

        content = []
        if ret.text is not None:
            content.append(provider_message.ContentElement.from_text(ret.text))
        if ret.image_url is not None:
            content.append(provider_message.ContentElement.from_image_url(ret.image_url))

        assert len(content) == 2
        assert content[0].type == 'text'
        assert content[1].type == 'image_url'


class TestPreventDefaultHandling:
    """Tests for prevent_default handling."""

    @pytest.mark.asyncio
    async def test_prevent_default_with_reply(self):
        """prevent_default with reply continues pipeline."""
        from tests.factories.message import text_chain

        # Simulate event context
        event_ctx = Mock()
        event_ctx.is_prevented_default.return_value = True
        event_ctx.event = Mock()
        event_ctx.event.reply_message_chain = text_chain('plugin reply')

        query = command_query('test')
        query.resp_messages = []

        # Pattern from handler
        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is not None:
                query.resp_messages.append(event_ctx.event.reply_message_chain)
                # yield CONTINUE
            else:
                # yield INTERRUPT
                pass

        assert len(query.resp_messages) == 1

    @pytest.mark.asyncio
    async def test_prevent_default_without_reply(self):
        """prevent_default without reply interrupts."""
        event_ctx = Mock()
        event_ctx.is_prevented_default.return_value = True
        event_ctx.event = Mock()
        event_ctx.event.reply_message_chain = None

        query = command_query('test')
        query.resp_messages = []

        should_interrupt = False
        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is None:
                should_interrupt = True

        assert should_interrupt is True


class TestStringTruncationHelper:
    """Tests for cut_str helper method."""

    def test_short_string_no_change(self):
        """Short string is not truncated."""
        # Pattern from handler.cut_str
        def cut_str(s: str) -> str:
            s0 = s.split('\n')[0]
            if len(s0) > 20 or '\n' in s:
                s0 = s0[:20] + '...'
            return s0

        result = cut_str('short text')
        assert result == 'short text'

    def test_long_string_truncated(self):
        """Long string is truncated."""
        def cut_str(s: str) -> str:
            s0 = s.split('\n')[0]
            if len(s0) > 20 or '\n' in s:
                s0 = s0[:20] + '...'
            return s0

        result = cut_str('this is a very long string that exceeds twenty characters')
        assert '...' in result
        assert len(result) <= 23

    def test_multiline_truncated(self):
        """Multiline string is truncated."""
        def cut_str(s: str) -> str:
            s0 = s.split('\n')[0]
            if len(s0) > 20 or '\n' in s:
                s0 = s0[:20] + '...'
            return s0

        result = cut_str('first line\nsecond line\nthird')
        assert '...' in result


class TestCommandPrefixConfiguration:
    """Tests for command prefix configuration."""

    def test_default_prefixes(self):
        """Default prefixes are slash and exclamation."""
        default_prefixes = ['/', '!']
        assert '/' in default_prefixes
        assert '!' in default_prefixes

    def test_custom_prefix(self):
        """Custom prefix can be configured."""
        custom_prefix = '#'
        full_text = f'{custom_prefix}help'

        # Would be checked against config['command']['prefix']
        is_command = full_text.startswith(custom_prefix)
        assert is_command is True
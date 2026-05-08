"""
Unit tests for CommandHandler - REAL imports.

Tests the actual CommandHandler class from production code.
Uses tests.utils.import_isolation to break circular import chain safely.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock

from tests.factories import FakeApp, command_query


# ============== FIXTURE USING IMPORT ISOLATION UTILITY ==============

@pytest.fixture(scope='module')
def mock_circular_import_chain():
    """
    Break circular import chain using isolated_sys_modules.

    Chain: handler → core.app → pipeline.controller → http_controller → groups/plugins → taskmgr

    Uses tests.utils.import_isolation for safe, reversible sys.modules manipulation.
    """
    from tests.utils.import_isolation import (
        isolated_sys_modules,
        make_pipeline_handler_import_mocks,
        get_handler_modules_to_clear,
    )

    mocks = make_pipeline_handler_import_mocks()
    clear = get_handler_modules_to_clear('command')

    with isolated_sys_modules(mocks=mocks, clear=clear):
        yield


@pytest.fixture
def fake_app():
    """Create FakeApp instance."""
    return FakeApp()


@pytest.fixture
def mock_event_ctx():
    """Create mock event context."""
    ctx = Mock()
    ctx.is_prevented_default = Mock(return_value=False)
    ctx.event = Mock()
    ctx.event.reply_message_chain = None
    return ctx


@pytest.fixture
def mock_execute_factory():
    """Factory fixture to create mock cmd_mgr.execute generators."""
    def _create_execute(
        text: str | None = 'ok',
        error: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
        file_url: str | None = None,
    ):
        async def mock_execute(command_text, full_command_text, query, session):
            ret = Mock()
            ret.text = text
            ret.error = error
            ret.image_url = image_url
            ret.image_base64 = image_base64
            ret.file_url = file_url
            yield ret
        return mock_execute
    return _create_execute


# ============== CACHED LAZY IMPORTS ==============

_command_handler_module = None
_entities_module = None


def get_command_handler():
    """Import CommandHandler after circular import chain is mocked."""
    global _command_handler_module
    if _command_handler_module is None:
        from importlib import import_module
        _command_handler_module = import_module('langbot.pkg.pipeline.process.handlers.command')
    return _command_handler_module


def get_entities():
    """Import pipeline entities - uses real module."""
    global _entities_module
    if _entities_module is None:
        from importlib import import_module
        _entities_module = import_module('langbot.pkg.pipeline.entities')
    return _entities_module


# ============== REAL CommandHandler Tests ==============

@pytest.mark.usefixtures('mock_circular_import_chain')
class TestCommandHandlerReal:
    """Tests for real CommandHandler class."""

    @pytest.mark.asyncio
    async def test_real_import_works(self):
        """Verify we can import the real handler class."""
        command = get_command_handler()
        assert hasattr(command, 'CommandHandler')
        handler_cls = command.CommandHandler
        assert handler_cls.__name__ == 'CommandHandler'

    @pytest.mark.asyncio
    async def test_handler_creation(self, fake_app):
        """CommandHandler can be instantiated."""
        command = get_command_handler()
        handler = command.CommandHandler(fake_app)
        assert handler.ap is fake_app

    @pytest.mark.asyncio
    async def test_command_parsing_extracts_command_name(self, fake_app, mock_event_ctx):
        """Command text is extracted after prefix."""
        command = get_command_handler()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        executed_commands = []
        async def track_execute(command_text, full_command_text, query, session):
            executed_commands.append(command_text)
            ret = Mock()
            ret.text = 'ok'
            ret.error = None
            ret.image_url = None
            ret.image_base64 = None
            ret.file_url = None
            yield ret

        fake_app.cmd_mgr.execute = track_execute

        handler = command.CommandHandler(fake_app)
        query = command_query('help arg1 arg2')

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert executed_commands[0] == 'help arg1 arg2'

    @pytest.mark.asyncio
    async def test_admin_privilege_check(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Admin users get privilege level 2."""
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

        command = get_command_handler()

        fake_app.instance_config.data = {'admins': ['person_12345']}
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory()

        handler = command.CommandHandler(fake_app)
        query = command_query('status')
        query.launcher_type = LauncherTypes.PERSON
        query.launcher_id = 12345

        results = []
        async for result in handler.handle(query):
            results.append(result)

        call_args = fake_app.plugin_connector.emit_event.call_args
        event = call_args[0][0]
        assert event.is_admin is True

    @pytest.mark.asyncio
    async def test_non_admin_privilege_check(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Non-admin users get privilege level 1."""
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

        command = get_command_handler()

        fake_app.instance_config.data = {'admins': ['person_12345']}
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory()

        handler = command.CommandHandler(fake_app)
        query = command_query('status')
        query.launcher_type = LauncherTypes.PERSON
        query.launcher_id = 67890

        results = []
        async for result in handler.handle(query):
            results.append(result)

        call_args = fake_app.plugin_connector.emit_event.call_args
        event = call_args[0][0]
        assert event.is_admin is False

    @pytest.mark.asyncio
    async def test_prevent_default_with_reply_continues(self, fake_app, mock_event_ctx):
        """prevent_default with reply yields CONTINUE."""
        from tests.factories.message import text_chain

        command = get_command_handler()
        entities = get_entities()

        reply_chain = text_chain('plugin reply')
        mock_event_ctx.is_prevented_default.return_value = True
        mock_event_ctx.event.reply_message_chain = reply_chain
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        handler = command.CommandHandler(fake_app)
        query = command_query('test')
        query.resp_messages = []

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        assert len(query.resp_messages) == 1
        assert query.resp_messages[0] == reply_chain

    @pytest.mark.asyncio
    async def test_prevent_default_without_reply_interrupts(self, fake_app, mock_event_ctx):
        """prevent_default without reply yields INTERRUPT."""
        command = get_command_handler()
        entities = get_entities()

        mock_event_ctx.is_prevented_default.return_value = True
        mock_event_ctx.event.reply_message_chain = None
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        handler = command.CommandHandler(fake_app)
        query = command_query('test')

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT

    @pytest.mark.asyncio
    async def test_event_type_person_command(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Person launcher creates PersonCommandSent event."""
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes
        from langbot_plugin.api.entities import events

        command = get_command_handler()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory()

        handler = command.CommandHandler(fake_app)
        query = command_query('help')
        query.launcher_type = LauncherTypes.PERSON

        results = []
        async for result in handler.handle(query):
            results.append(result)

        call_args = fake_app.plugin_connector.emit_event.call_args
        event = call_args[0][0]
        assert isinstance(event, events.PersonCommandSent)

    @pytest.mark.asyncio
    async def test_event_type_group_command(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Group launcher creates GroupCommandSent event."""
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes
        from langbot_plugin.api.entities import events

        command = get_command_handler()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory()

        handler = command.CommandHandler(fake_app)
        query = command_query('help')
        query.launcher_type = LauncherTypes.GROUP

        results = []
        async for result in handler.handle(query):
            results.append(result)

        call_args = fake_app.plugin_connector.emit_event.call_args
        event = call_args[0][0]
        assert isinstance(event, events.GroupCommandSent)

    @pytest.mark.asyncio
    async def test_command_result_text(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Text result is added to resp_messages."""
        command = get_command_handler()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory(text='Command output')

        handler = command.CommandHandler(fake_app)
        query = command_query('echo')
        query.resp_messages = []

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(query.resp_messages) == 1
        msg = query.resp_messages[0]
        assert msg.role == 'command'
        assert len(msg.content) == 1
        assert msg.content[0].type == 'text'
        assert msg.content[0].text == 'Command output'

    @pytest.mark.asyncio
    async def test_command_result_error(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Error result creates error message."""
        command = get_command_handler()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory(text=None, error='Command failed')

        handler = command.CommandHandler(fake_app)
        query = command_query('fail')
        query.resp_messages = []

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(query.resp_messages) == 1
        msg = query.resp_messages[0]
        assert msg.role == 'command'
        assert msg.content == 'Command failed'

    @pytest.mark.asyncio
    async def test_command_result_image_url(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Image URL result is added to content."""
        command = get_command_handler()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory(
            text='Here is the image:',
            image_url='https://example.com/image.png'
        )

        handler = command.CommandHandler(fake_app)
        query = command_query('image')
        query.resp_messages = []

        results = []
        async for result in handler.handle(query):
            results.append(result)

        msg = query.resp_messages[0]
        assert len(msg.content) == 2
        assert msg.content[0].type == 'text'
        assert msg.content[1].type == 'image_url'

    @pytest.mark.asyncio
    async def test_command_result_empty_interrupts(self, fake_app, mock_event_ctx, mock_execute_factory):
        """Empty result yields INTERRUPT."""
        command = get_command_handler()
        entities = get_entities()
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        fake_app.cmd_mgr.execute = mock_execute_factory(text=None)

        handler = command.CommandHandler(fake_app)
        query = command_query('empty')

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert results[0].result_type == entities.ResultType.INTERRUPT


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestCommandHandlerHelper:
    """Tests for helper methods."""

    def test_cut_str_short(self, fake_app):
        """cut_str returns short string unchanged."""
        command = get_command_handler()
        handler = command.CommandHandler(fake_app)
        result = handler.cut_str('short text')
        assert result == 'short text'

    def test_cut_str_long(self, fake_app):
        """cut_str truncates long string."""
        command = get_command_handler()
        handler = command.CommandHandler(fake_app)
        result = handler.cut_str('this is a very long string that exceeds twenty characters')
        assert '...' in result
        assert len(result) <= 23

    def test_cut_str_multiline(self, fake_app):
        """cut_str truncates multiline string."""
        command = get_command_handler()
        handler = command.CommandHandler(fake_app)
        result = handler.cut_str('first line\nsecond line')
        assert '...' in result
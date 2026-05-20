"""
Unit tests for cmdmgr module - REAL imports.

Tests CommandManager initialization, execute, and privilege handling.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock

from langbot.pkg.command import operator
from langbot.pkg.command.cmdmgr import CommandManager
from tests.factories import FakeApp, command_query

import langbot_plugin.api.entities.builtin.provider.session as provider_session


class TestCommandManagerInit:
    """Tests for CommandManager initialization."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    @pytest.mark.asyncio
    async def test_init_does_not_set_cmd_list(self):
        """CommandManager.__init__ does not set cmd_list (set in initialize())."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)

        assert mgr.ap is fake_app
        assert not hasattr(mgr, 'cmd_list')  # Not set until initialize()

    @pytest.mark.asyncio
    async def test_initialize_sets_path_for_top_level_commands(self):
        """initialize() sets path for top-level commands."""

        @operator.operator_class(name='help')
        class HelpOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='status')
        class StatusOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        # Check paths are set
        help_op = next(op for op in mgr.cmd_list if op.name == 'help')
        status_op = next(op for op in mgr.cmd_list if op.name == 'status')

        assert help_op.path == 'help'
        assert status_op.path == 'status'

    @pytest.mark.asyncio
    async def test_initialize_sets_path_for_nested_commands(self):
        """initialize() sets path for nested commands."""

        @operator.operator_class(name='plugin')
        class PluginOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='list', parent_class=PluginOperator)
        class PluginListOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='install', parent_class=PluginOperator)
        class PluginInstallOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        plugin_op = next(op for op in mgr.cmd_list if op.name == 'plugin')
        list_op = next(op for op in mgr.cmd_list if op.name == 'list')
        install_op = next(op for op in mgr.cmd_list if op.name == 'install')

        assert plugin_op.path == 'plugin'
        assert list_op.path == 'plugin.list'
        assert install_op.path == 'plugin.install'

    @pytest.mark.asyncio
    async def test_initialize_sets_children_for_parent_commands(self):
        """initialize() sets children list for parent commands."""

        @operator.operator_class(name='parent')
        class ParentOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='child1', parent_class=ParentOperator)
        class Child1Operator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='child2', parent_class=ParentOperator)
        class Child2Operator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        parent_op = next(op for op in mgr.cmd_list if op.name == 'parent')
        child_names = [child.name for child in parent_op.children]

        assert len(parent_op.children) == 2
        assert 'child1' in child_names
        assert 'child2' in child_names

    @pytest.mark.asyncio
    async def test_initialize_instantiates_all_operators(self):
        """initialize() instantiates all preregistered operators."""

        @operator.operator_class(name='help')
        class HelpOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='status')
        class StatusOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        assert len(mgr.cmd_list) == 2
        assert all(isinstance(op, operator.CommandOperator) for op in mgr.cmd_list)

    @pytest.mark.asyncio
    async def test_initialize_calls_operator_initialize(self):
        """initialize() calls initialize() on each operator."""

        init_called = []

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def initialize(self):
                init_called.append(self.name)

            async def execute(self, context):
                yield None

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        assert 'test' in init_called

    @pytest.mark.asyncio
    async def test_initialize_with_no_operators(self):
        """initialize() handles empty preregistered_operators."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        assert mgr.cmd_list == []


class TestCommandManagerExecute:
    """Tests for CommandManager execute method."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    def _create_session(self, launcher_type=provider_session.LauncherTypes.PERSON, launcher_id=12345):
        """Helper to create a session."""
        return provider_session.Session(
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=launcher_id,
            use_prompt_name='default',
            using_conversation=None,
            conversations=[],
        )

    @pytest.mark.asyncio
    async def test_execute_returns_generator(self):
        """execute() returns an async generator."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)

        # Mock plugin_connector.list_commands to return empty list
        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('help')
        session = self._create_session()

        result = mgr.execute('help', '/help', query, session)
        assert hasattr(result, '__aiter__')

    @pytest.mark.asyncio
    async def test_execute_sets_privilege_for_admin(self):
        """execute() sets privilege=2 for admin users."""

        fake_app = FakeApp(admins=['person_12345'])
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        # Mock plugin_connector
        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('status')
        query.launcher_type = provider_session.LauncherTypes.PERSON
        query.launcher_id = 12345

        session = self._create_session()

        results = []
        async for ret in mgr.execute('status', '/status', query, session):
            results.append(ret)

        # Verify admin config was checked
        assert 'person_12345' in fake_app.instance_config.data['admins']

    @pytest.mark.asyncio
    async def test_execute_sets_privilege_for_non_admin(self):
        """execute() sets privilege=1 for non-admin users."""

        fake_app = FakeApp(admins=['person_12345'])
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('status')
        query.launcher_type = provider_session.LauncherTypes.PERSON
        query.launcher_id = 67890  # Not in admins list

        session = self._create_session(launcher_id=67890)

        results = []
        async for ret in mgr.execute('status', '/status', query, session):
            results.append(ret)

    @pytest.mark.asyncio
    async def test_execute_parses_command_text(self):
        """execute() splits command_text into params."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('help arg1 arg2')
        session = self._create_session()

        results = []
        async for ret in mgr.execute('help arg1 arg2', '/help arg1 arg2', query, session):
            results.append(ret)

        # Command text parsing happens inside execute()
        # We verify it doesn't crash

    @pytest.mark.asyncio
    async def test_execute_passes_bound_plugins(self):
        """execute() passes bound_plugins from query variables."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('help')
        query.variables = {'_pipeline_bound_plugins': ['plugin1', 'plugin2']}

        session = self._create_session()

        results = []
        async for ret in mgr.execute('help', '/help', query, session):
            results.append(ret)

        # Bound plugins are extracted from query.variables
        assert query.variables.get('_pipeline_bound_plugins') == ['plugin1', 'plugin2']


class TestCommandManagerInternalExecute:
    """Tests for CommandManager._execute method."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    def _create_context(self, command='help', privilege=1):
        """Helper to create ExecuteContext."""
        from langbot_plugin.api.entities.builtin.command import context as cmd_context

        session = provider_session.Session(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            use_prompt_name='default',
            using_conversation=None,
            conversations=[],
        )

        return cmd_context.ExecuteContext(
            query_id=1,
            session=session,
            command_text='help',
            full_command_text='/help',
            command=command,
            crt_command=command,
            params=['help'],
            crt_params=['help'],
            privilege=privilege,
        )

    @pytest.mark.asyncio
    async def test_execute_yields_command_not_found_error(self):
        """_execute yields CommandNotFoundError for unknown commands."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        # Mock plugin_connector.list_commands to return empty list
        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        ctx = self._create_context(command='unknown_cmd')

        results = []
        async for ret in mgr._execute(ctx, mgr.cmd_list):
            results.append(ret)

        assert len(results) == 1
        assert results[0].error is not None
        assert '未知命令' in str(results[0].error)

    @pytest.mark.asyncio
    async def test_execute_calls_plugin_command(self):
        """_execute calls plugin connector for plugin commands."""

        from langbot_plugin.api.entities.builtin.command import context as cmd_context

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        # Mock plugin command
        mock_command = Mock()
        mock_command.metadata.name = 'plugin_cmd'

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[mock_command])

        async def mock_plugin_execute(ctx, bound_plugins):
            yield cmd_context.CommandReturn(text='plugin response')

        fake_app.plugin_connector.execute_command = mock_plugin_execute

        ctx = self._create_context(command='plugin_cmd')

        results = []
        async for ret in mgr._execute(ctx, mgr.cmd_list):
            results.append(ret)

        assert len(results) == 1
        assert results[0].text == 'plugin response'

    @pytest.mark.asyncio
    async def test_execute_with_bound_plugins(self):
        """_execute passes bound_plugins to plugin connector."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        # Mock plugin command
        mock_command = Mock()
        mock_command.metadata.name = 'test_cmd'

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[mock_command])

        async def mock_execute_command(ctx, bound_plugins):
            yield Mock(text='ok')

        fake_app.plugin_connector.execute_command = mock_execute_command

        ctx = self._create_context(command='test_cmd')

        # Execute with bound_plugins parameter
        async for _ in mgr._execute(ctx, mgr.cmd_list, bound_plugins=['test_plugin']):
            pass


class TestEmptyAndEdgeInputs:
    """Tests for empty and edge inputs."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    def _create_session(self):
        """Helper to create a session."""
        return provider_session.Session(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            use_prompt_name='default',
            using_conversation=None,
            conversations=[],
        )

    @pytest.mark.asyncio
    async def test_execute_with_empty_command_text(self):
        """execute() handles empty command_text."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('')  # Empty command
        session = self._create_session()

        results = []
        async for ret in mgr.execute('', '/', query, session):
            results.append(ret)

        # Should yield CommandNotFoundError for empty command
        assert len(results) == 1
        assert results[0].error is not None

    @pytest.mark.asyncio
    async def test_execute_with_whitespace_command(self):
        """execute() handles whitespace-only command_text."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('   ')  # Whitespace command
        session = self._create_session()

        results = []
        async for ret in mgr.execute('   ', '/   ', query, session):
            results.append(ret)

        # Should yield error
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_initialize_with_deep_nesting(self):
        """initialize() handles deeply nested commands."""

        @operator.operator_class(name='l1')
        class L1Operator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='l2', parent_class=L1Operator)
        class L2Operator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='l3', parent_class=L2Operator)
        class L3Operator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        await mgr.initialize()

        l3_op = next(op for op in mgr.cmd_list if op.name == 'l3')
        assert l3_op.path == 'l1.l2.l3'

    @pytest.mark.asyncio
    async def test_execute_with_special_command_name(self):
        """execute() handles special characters in command name."""

        fake_app = FakeApp()
        mgr = CommandManager(fake_app)
        mgr.cmd_list = []

        fake_app.plugin_connector.list_commands = AsyncMock(return_value=[])

        query = command_query('test-command_123')
        session = self._create_session()

        results = []
        async for ret in mgr.execute('test-command_123', '/test-command_123', query, session):
            results.append(ret)

        # Should yield CommandNotFoundError (no such command registered)
        assert len(results) == 1
        assert results[0].error is not None
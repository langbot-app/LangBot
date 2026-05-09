"""
Unit tests for operator module - REAL imports.

Tests the operator_class decorator and CommandOperator base class.
"""

from __future__ import annotations

import pytest

from langbot.pkg.command import operator


class TestOperatorClassDecorator:
    """Tests for operator_class decorator."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    def test_decorator_sets_name(self):
        """Decorator sets command name on class."""

        @operator.operator_class(name='test_cmd')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.name == 'test_cmd'

    def test_decorator_sets_help(self):
        """Decorator sets help text on class."""

        @operator.operator_class(name='test', help='Test help message')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.help == 'Test help message'

    def test_decorator_sets_usage(self):
        """Decorator sets usage text on class."""

        @operator.operator_class(name='test', usage='!test <arg>')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.usage == '!test <arg>'

    def test_decorator_sets_alias(self):
        """Decorator sets alias list on class."""

        @operator.operator_class(name='test', alias=['t', 'tst'])
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.alias == ['t', 'tst']

    def test_decorator_sets_privilege_default(self):
        """Decorator sets default privilege to 1 (normal user)."""

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.lowest_privilege == 1

    def test_decorator_sets_privilege_admin(self):
        """Decorator sets privilege to 2 for admin commands."""

        @operator.operator_class(name='admin_cmd', privilege=2)
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.lowest_privilege == 2

    def test_decorator_sets_parent_class_none(self):
        """Decorator sets parent_class to None for top-level commands."""

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator.parent_class is None

    def test_decorator_sets_parent_class(self):
        """Decorator sets parent_class for sub-commands."""

        @operator.operator_class(name='parent')
        class ParentOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='child', parent_class=ParentOperator)
        class ChildOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert ChildOperator.parent_class is ParentOperator

    def test_decorator_registers_to_preregistered_list(self):
        """Decorator appends class to preregistered_operators."""

        @operator.operator_class(name='test1')
        class TestOperator1(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='test2')
        class TestOperator2(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert TestOperator1 in operator.preregistered_operators
        assert TestOperator2 in operator.preregistered_operators

    def test_decorator_requires_command_operator_subclass(self):
        """Decorator asserts class is subclass of CommandOperator."""

        with pytest.raises(AssertionError):
            operator.operator_class(name='invalid')(object)


class TestCommandOperatorBase:
    """Tests for CommandOperator base class."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    def test_init_sets_app(self):
        """__init__ stores application reference."""

        class MockApp:
            pass

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        app = MockApp()
        op = TestOperator(app)
        assert op.ap is app

    def test_init_sets_empty_children(self):
        """__init__ initializes empty children list."""

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        op = TestOperator(None)
        assert op.children == []

    def test_class_has_required_attributes(self):
        """CommandOperator has required class attributes."""

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert hasattr(TestOperator, 'name')
        assert hasattr(TestOperator, 'alias')
        assert hasattr(TestOperator, 'help')
        assert hasattr(TestOperator, 'usage')
        assert hasattr(TestOperator, 'parent_class')
        assert hasattr(TestOperator, 'lowest_privilege')

    def test_initialize_is_async_noop(self):
        """Default initialize() is async no-op."""

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        op = TestOperator(None)
        # Should not raise
        import asyncio
        asyncio.get_event_loop().run_until_complete(op.initialize())

    def test_execute_is_abstract(self):
        """execute() must be implemented by subclass."""

        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            operator.CommandOperator(None)

    def test_path_not_set_by_decorator(self):
        """path is not set by decorator, set by CommandManager."""

        @operator.operator_class(name='test')
        class TestOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        # path should not exist initially
        assert not hasattr(TestOperator, 'path') or TestOperator.path is None


class TestMultipleOperators:
    """Tests for multiple operator registration and hierarchy."""

    def setup_method(self):
        """Save and clear preregistered_operators before each test."""
        self._saved_operators = operator.preregistered_operators.copy()
        operator.preregistered_operators.clear()

    def teardown_method(self):
        """Restore preregistered_operators after each test."""
        operator.preregistered_operators.clear()
        operator.preregistered_operators.extend(self._saved_operators)

    def test_multiple_independent_operators(self):
        """Multiple independent operators can be registered."""

        @operator.operator_class(name='help')
        class HelpOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='status')
        class StatusOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='version')
        class VersionOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert len(operator.preregistered_operators) == 3
        names = [op.name for op in operator.preregistered_operators]
        assert 'help' in names
        assert 'status' in names
        assert 'version' in names

    def test_parent_child_hierarchy(self):
        """Parent-child hierarchy can be established."""

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

        # Both parent and children are in preregistered list
        assert len(operator.preregistered_operators) == 3

        # Parent-child relationships are established via parent_class
        plugin_op = next(op for op in operator.preregistered_operators if op.name == 'plugin')
        list_op = next(op for op in operator.preregistered_operators if op.name == 'list')
        install_op = next(op for op in operator.preregistered_operators if op.name == 'install')

        assert plugin_op.parent_class is None
        assert list_op.parent_class is PluginOperator
        assert install_op.parent_class is PluginOperator

    def test_privilege_inheritance_not_automatic(self):
        """Child operators do not automatically inherit parent privilege."""

        @operator.operator_class(name='admin', privilege=2)
        class AdminOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        @operator.operator_class(name='sub', parent_class=AdminOperator, privilege=1)
        class SubOperator(operator.CommandOperator):
            async def execute(self, context):
                yield None

        assert AdminOperator.lowest_privilege == 2
        assert SubOperator.lowest_privilege == 1
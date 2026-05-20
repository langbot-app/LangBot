"""Unit tests for persistence database decorators.

Tests cover:
- manager_class decorator registration
- Class attribute setting
- preregistered_managers list population

Note: Uses import isolation to break circular import chains.
"""
from __future__ import annotations

import sys
from unittest.mock import Mock, MagicMock
from contextlib import contextmanager
from typing import Generator


@contextmanager
def isolated_database_import() -> Generator[None, None, None]:
    """Context manager to isolate circular imports for database testing."""
    # Mock modules that cause circular imports
    mock_app = MagicMock()

    mock_importutil = MagicMock()
    mock_importutil.import_modules_in_pkg = lambda pkg: None
    mock_importutil.import_modules_in_pkgs = lambda pkgs: None

    mock_mgr = MagicMock()

    mocks = {
        'langbot.pkg.core.app': mock_app,
        'langbot.pkg.utils.importutil': mock_importutil,
        'langbot.pkg.persistence.mgr': mock_mgr,
    }

    # Save original state
    saved = {}
    for name in mocks:
        if name in sys.modules:
            saved[name] = sys.modules[name]

    # Clear database module to force re-import
    database_name = 'langbot.pkg.persistence.database'
    if database_name in sys.modules:
        saved[database_name] = sys.modules[database_name]

    # Also clear databases submodules
    for sub in ['sqlite', 'postgresql']:
        full_name = f'langbot.pkg.persistence.databases.{sub}'
        if full_name in sys.modules:
            saved[full_name] = sys.modules[full_name]

    try:
        # Apply mocks
        for name, module in mocks.items():
            sys.modules[name] = module

        # Clear database and submodules
        sys.modules.pop(database_name, None)
        for sub in ['sqlite', 'postgresql']:
            sys.modules.pop(f'langbot.pkg.persistence.databases.{sub}', None)

        yield
    finally:
        # Restore
        for name in mocks:
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)

        if database_name in saved:
            sys.modules[database_name] = saved[database_name]
        else:
            sys.modules.pop(database_name, None)

        for sub in ['sqlite', 'postgresql']:
            full_name = f'langbot.pkg.persistence.databases.{sub}'
            if full_name in saved:
                sys.modules[full_name] = saved[full_name]
            else:
                sys.modules.pop(full_name, None)


def get_database_module():
    """Get database module with import isolation."""
    with isolated_database_import():
        from langbot.pkg.persistence import database
        return database


class TestManagerClassDecorator:
    """Tests for manager_class decorator."""

    def test_decorator_sets_name_attribute(self):
        """Test that decorator sets the 'name' attribute on class."""
        database = get_database_module()

        # Clear preregistered_managers for this test
        database.preregistered_managers.clear()

        @database.manager_class('test_db')
        class TestManager(database.BaseDatabaseManager):
            async def initialize(self):
                pass

        assert TestManager.name == 'test_db'

    def test_decorator_adds_to_preregistered_list(self):
        """Test that decorator adds class to preregistered_managers."""
        database = get_database_module()

        # Clear preregistered_managers for this test
        database.preregistered_managers.clear()

        @database.manager_class('test_db2')
        class TestManager2(database.BaseDatabaseManager):
            async def initialize(self):
                pass

        assert len(database.preregistered_managers) == 1
        assert database.preregistered_managers[0] == TestManager2

    def test_decorator_returns_original_class(self):
        """Test that decorator returns the same class."""
        database = get_database_module()

        database.preregistered_managers.clear()

        class OriginalClass(database.BaseDatabaseManager):
            async def initialize(self):
                pass

        decorated = database.manager_class('test_db3')(OriginalClass)

        assert decorated is OriginalClass

    def test_multiple_decorators_register_separately(self):
        """Test that multiple decorated classes register separately."""
        database = get_database_module()

        database.preregistered_managers.clear()

        @database.manager_class('db_a')
        class ManagerA(database.BaseDatabaseManager):
            async def initialize(self):
                pass

        @database.manager_class('db_b')
        class ManagerB(database.BaseDatabaseManager):
            async def initialize(self):
                pass

        assert len(database.preregistered_managers) == 2
        assert database.preregistered_managers[0].name == 'db_a'
        assert database.preregistered_managers[1].name == 'db_b'

    def test_base_database_manager_has_name_annotation(self):
        """Test that BaseDatabaseManager has name as class annotation."""
        database = get_database_module()

        # BaseDatabaseManager has name annotation (type hint)
        # Check __annotations__ for the type hint
        assert 'name' in database.BaseDatabaseManager.__annotations__

    def test_decorated_class_inherits_from_base(self):
        """Test that decorated class properly inherits BaseDatabaseManager."""
        database = get_database_module()

        database.preregistered_managers.clear()

        @database.manager_class('test_inherit')
        class TestChild(database.BaseDatabaseManager):
            async def initialize(self):
                pass

        assert issubclass(TestChild, database.BaseDatabaseManager)
        # Has abstract method requirement satisfied
        assert hasattr(TestChild, 'initialize')

    def test_decorator_preserves_class_methods(self):
        """Test that decorator preserves existing class methods."""
        database = get_database_module()

        database.preregistered_managers.clear()

        @database.manager_class('preserve_test')
        class ManagerWithMethods(database.BaseDatabaseManager):
            custom_attr = 'test_value'

            async def initialize(self):
                pass

            def custom_method(self):
                return self.custom_attr

        assert ManagerWithMethods.custom_attr == 'test_value'
        # Create instance to test method (with mock app)
        mock_app = Mock()
        instance = ManagerWithMethods(mock_app)
        assert instance.custom_method() == 'test_value'
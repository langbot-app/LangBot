"""Tests for core migration registration and abstract classes."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from tests.utils.import_isolation import isolated_sys_modules


class TestMigrationClassDecorator:
    """Tests for @migration_class decorator."""

    def _make_migration_import_mocks(self):
        """Create mocks for migration import."""
        return {
            'langbot.pkg.core.app': MagicMock(),
        }

    def test_migration_class_registers_migration(self):
        """@migration_class registers migration in preregistered_migrations."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import migration_class, preregistered_migrations

            # Clear for clean test
            preregistered_migrations.clear()

            @migration_class('test-migration', 1)
            class TestMigration:
                pass

            assert len(preregistered_migrations) == 1
            assert preregistered_migrations[0] == TestMigration

    def test_migration_class_sets_name_attribute(self):
        """@migration_class sets name attribute on class."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import migration_class

            @migration_class('test-migration', 1)
            class TestMigration:
                pass

            assert TestMigration.name == 'test-migration'

    def test_migration_class_sets_number_attribute(self):
        """@migration_class sets number attribute on class."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import migration_class

            @migration_class('test-migration', 42)
            class TestMigration:
                pass

            assert TestMigration.number == 42

    def test_migration_class_returns_original_class(self):
        """@migration_class returns the original class."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import migration_class

            @migration_class('test', 1)
            class TestMigration:
                custom_attr = 'value'

            assert TestMigration.custom_attr == 'value'

    def test_migration_class_multiple_migrations(self):
        """Multiple migrations can be registered."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import migration_class, preregistered_migrations

            preregistered_migrations.clear()

            @migration_class('migration1', 1)
            class Migration1:
                pass

            @migration_class('migration2', 2)
            class Migration2:
                pass

            assert len(preregistered_migrations) == 2
            assert preregistered_migrations[0] == Migration1
            assert preregistered_migrations[1] == Migration2


class TestMigrationAbstractClass:
    """Tests for Migration abstract class."""

    def _make_migration_import_mocks(self):
        return {'langbot.pkg.core.app': MagicMock()}

    def test_migration_is_abstract(self):
        """Migration is abstract and cannot be instantiated directly."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import Migration

            with pytest.raises(TypeError):
                Migration(MagicMock())

    def test_migration_requires_need_migrate_method(self):
        """Subclass must implement need_migrate method."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import Migration

            class IncompleteMigration(Migration):
                async def run(self):
                    pass

            with pytest.raises(TypeError):
                IncompleteMigration(MagicMock())

    def test_migration_requires_run_method(self):
        """Subclass must implement run method."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import Migration

            class IncompleteMigration(Migration):
                async def need_migrate(self) -> bool:
                    return False

            with pytest.raises(TypeError):
                IncompleteMigration(MagicMock())

    def test_migration_subclass_works(self):
        """Complete subclass can be instantiated."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import Migration

            class CompleteMigration(Migration):
                async def need_migrate(self) -> bool:
                    return True

                async def run(self):
                    pass

            mock_ap = MagicMock()
            migration = CompleteMigration(mock_ap)
            assert migration.ap == mock_ap

    def test_migration_stores_app_reference(self):
        """Migration stores ap reference in __init__."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import Migration

            class TestMigration(Migration):
                async def need_migrate(self) -> bool:
                    return False

                async def run(self):
                    pass

            mock_ap = MagicMock()
            migration = TestMigration(mock_ap)
            assert migration.ap is mock_ap

    @pytest.mark.asyncio
    async def test_migration_need_migrate_returns_bool(self):
        """need_migrate must return bool."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import Migration

            class TestMigration(Migration):
                async def need_migrate(self) -> bool:
                    return True

                async def run(self):
                    pass

            migration = TestMigration(MagicMock())
            result = await migration.need_migrate()
            assert isinstance(result, bool)
            assert result == True


class TestPreregisteredMigrations:
    """Tests for preregistered_migrations global registry."""

    def _make_migration_import_mocks(self):
        return {'langbot.pkg.core.app': MagicMock()}

    def test_preregistered_migrations_is_list(self):
        """preregistered_migrations is a list."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import preregistered_migrations

            assert isinstance(preregistered_migrations, list)

    def test_preregistered_migrations_order(self):
        """Migrations are registered in order of decoration."""
        mocks = self._make_migration_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.migration import migration_class, preregistered_migrations

            preregistered_migrations.clear()

            @migration_class('first', 1)
            class First:
                pass

            @migration_class('second', 2)
            class Second:
                pass

            @migration_class('third', 3)
            class Third:
                pass

            # Order should match decoration order
            assert preregistered_migrations[0].number == 1
            assert preregistered_migrations[1].number == 2
            assert preregistered_migrations[2].number == 3
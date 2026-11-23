"""The permission migration supports both upgraded and fresh schemas."""

import importlib
import json

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa


@pytest.mark.parametrize('fresh_schema', [False, True])
def test_plugin_permission_columns_preserve_existing_installs(fresh_schema):
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0044_plugin_permissions')
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        columns = [sa.Column('id', sa.Integer, primary_key=True)]
        names = ('permission_declaration', 'permission_grants', 'permission_snapshot')
        if fresh_schema:
            columns.extend(sa.Column(name, sa.JSON, nullable=True) for name in names)
        table = sa.Table('plugin_settings', sa.MetaData(), *columns)
        table.create(connection)
        connection.execute(table.insert().values(id=1))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        existing = {column['name'] for column in sa.inspect(connection).get_columns('plugin_settings')}
        assert set(names) <= existing
        row = connection.execute(
            sa.text(
                'SELECT permission_declaration, permission_grants, permission_snapshot FROM plugin_settings WHERE id = 1'
            )
        ).one()
        expected = {'workspace_operations': [], 'capabilities': migration.LEGACY_CAPABILITIES}
        assert row.permission_declaration is None
        assert json.loads(row.permission_grants) == json.loads(row.permission_snapshot) == expected
    engine.dispose()

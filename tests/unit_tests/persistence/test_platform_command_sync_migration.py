import importlib
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_platform_command_sync_upgrade_and_downgrade():
    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0044_platform_command_sync')
    assert migration.down_revision == '0043_bot_command_settings'
    engine = sa.create_engine('sqlite://')
    metadata = sa.MetaData()
    bots = sa.Table('bots', metadata, sa.Column('uuid', sa.String(), primary_key=True))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(bots.insert().values(uuid='one'))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            migration.upgrade()
            migration.upgrade()
            upgraded = sa.Table('bots', sa.MetaData(), autoload_with=connection)
            assert connection.execute(sa.select(upgraded.c.platform_command_sync)).scalar_one() == {}
            migration.downgrade()
            migration.downgrade()
            assert [column['name'] for column in sa.inspect(connection).get_columns('bots')] == ['uuid']

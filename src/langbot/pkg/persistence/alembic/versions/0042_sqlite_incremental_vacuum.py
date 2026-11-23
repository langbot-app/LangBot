"""Enable bounded online SQLite space reclamation."""

from alembic import op

revision = '0042_sqlite_incremental_vacuum'
down_revision = '0041_resource_urls'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != 'sqlite':
        return
    with op.get_context().autocommit_block():
        mode = connection.exec_driver_sql('PRAGMA auto_vacuum').scalar_one()
        if mode != 2:
            connection.exec_driver_sql('PRAGMA auto_vacuum=INCREMENTAL')
            if mode == 0:
                connection.exec_driver_sql('VACUUM')
        if connection.exec_driver_sql('PRAGMA auto_vacuum').scalar_one() != 2:
            raise RuntimeError('SQLite incremental vacuum conversion did not complete')


def downgrade():
    # The physical format remains compatible with earlier releases. Do not
    # rebuild the database merely to undo a space reclamation preference.
    pass

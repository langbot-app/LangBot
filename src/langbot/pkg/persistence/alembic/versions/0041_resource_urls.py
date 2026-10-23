"""Normalize retained resource URLs behind stable shared references."""

import datetime
import json

from alembic import op
import sqlalchemy as sa

revision = '0041_resource_urls'
down_revision = '0040_session_summaries'
branch_labels = None
depends_on = None


def upgrade():
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.entity.persistence.resource_url import ResourceURL
    from langbot.pkg.persistence.media import MediaReferenceText, MediaReferenceJSON
    from langbot.pkg.persistence.resource_urls import create_postgres_expansion, intern, install

    connection = op.get_bind()
    ResourceURL.__table__.create(connection, checkfirst=True)
    op.drop_index('ix_resource_urls_canonical_id', table_name='resource_urls', if_exists=True)
    op.drop_index('ix_resource_urls_last_checked', table_name='resource_urls', if_exists=True)
    install(connection.engine)
    if connection.dialect.name == 'postgresql':
        create_postgres_expansion(connection)
    inspector = sa.inspect(connection)
    existing = set(inspector.get_table_names())
    for table in sorted(Base.metadata.tables.values(), key=lambda table: table.name):
        if table.name not in existing:
            continue
        retained = [
            column.name for column in table.columns if isinstance(column.type, (MediaReferenceText, MediaReferenceJSON))
        ]
        json_columns = {column.name for column in table.columns if isinstance(column.type, MediaReferenceJSON)}
        if not retained:
            continue
        # Reflection intentionally reads literal stored values without expansion.
        # Only local columns are needed; historical schemas may omit FK targets.
        source = sa.Table(table.name, sa.MetaData(), autoload_with=connection, resolve_fks=False)
        retained = [name for name in retained if name in source.c]
        keys = list(source.primary_key.columns)
        if len(keys) != 1:
            raise RuntimeError(f'Resource URL migration requires one primary key: {table.name}')
        key = keys[0]
        cursor = None
        stamp = source.c.get('created_at')
        if stamp is None:
            stamp = source.c.get('timestamp')
        while True:
            query = sa.select(source).order_by(key).limit(100)
            if cursor is not None:
                query = query.where(key > cursor)
            rows = connection.execute(query).mappings().all()
            if not rows:
                break
            for row in rows:
                created = row[stamp.name] if stamp is not None else None
                if created is not None and created.tzinfo is not None:
                    created = created.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                updates = {}
                for name in retained:
                    raw = json.dumps(row[name]) if name in json_columns else row[name]
                    converted = intern(connection, raw, created)
                    updates[name] = json.loads(converted) if name in json_columns else converted
                updates = {name: value for name, value in updates.items() if value != row[name]}
                if updates:
                    connection.execute(source.update().where(key == row[key.name]).values(**updates))
            cursor = rows[-1][key.name]


def downgrade():
    from langbot.pkg.entity.persistence.base import Base
    from langbot.pkg.persistence.media import MediaReferenceText, MediaReferenceJSON
    from langbot.pkg.persistence.resource_urls import uninstall

    connection = op.get_bind()
    existing = set(sa.inspect(connection).get_table_names())
    for table in sorted(Base.metadata.tables.values(), key=lambda table: table.name):
        if table.name not in existing:
            continue
        columns = {column['name'] for column in sa.inspect(connection).get_columns(table.name)}
        for column in table.columns:
            if column.name in columns and isinstance(column.type, (MediaReferenceText, MediaReferenceJSON)):
                name = connection.dialect.identifier_preparer.quote(table.name)
                field = connection.dialect.identifier_preparer.quote(column.name)
                expanded = f'langbot_expand_resource_urls(CAST({field} AS TEXT))'
                if isinstance(column.type, MediaReferenceJSON) and connection.dialect.name == 'postgresql':
                    expanded = f'CAST({expanded} AS JSON)'
                connection.exec_driver_sql(f'UPDATE {name} SET {field} = {expanded}')
    op.drop_table('resource_urls')
    if connection.dialect.name == 'postgresql':
        connection.exec_driver_sql('DROP FUNCTION langbot_expand_resource_urls(text)')
    uninstall(connection.engine)

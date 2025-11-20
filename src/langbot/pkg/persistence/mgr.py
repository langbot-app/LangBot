from __future__ import annotations

import datetime
import typing
import json
import uuid

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy

from . import database, migration
from ..entity.persistence import base, pipeline, metadata
from ..entity import persistence
from ..core import app
from ..utils import constants, importutil
from ..api.http.service import pipeline as pipeline_service
from . import databases, migrations

importutil.import_modules_in_pkg(databases)
importutil.import_modules_in_pkg(migrations)
importutil.import_modules_in_pkg(persistence)


class PersistenceManager:
    """Persistence module manager"""

    ap: app.Application

    db: database.BaseDatabaseManager
    """Database manager"""

    meta: sqlalchemy.MetaData

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.meta = base.Base.metadata

    async def initialize(self):
        database_type = self.ap.instance_config.data.get('database', {}).get('use', 'sqlite')
        self.ap.logger.info(f'Initializing database type: {database_type}...')
        for manager in database.preregistered_managers:
            if manager.name == database_type:
                self.db = manager(self.ap)
                await self.db.initialize()
                break

        await self.create_tables()

        # run migrations
        database_version = await self.execute_async(
            sqlalchemy.select(metadata.Metadata).where(metadata.Metadata.key == 'database_version')
        )

        database_version = int(database_version.fetchone()[1])
        required_database_version = constants.required_database_version

        if database_version < required_database_version:
            migrations = migration.preregistered_db_migrations
            migrations.sort(key=lambda x: x.number)

            last_migration_number = database_version

            for migration_cls in migrations:
                migration_instance = migration_cls(self.ap)

                if (
                    migration_instance.number > database_version
                    and migration_instance.number <= required_database_version
                ):
                    await migration_instance.upgrade()
                    await self.execute_async(
                        sqlalchemy.update(metadata.Metadata)
                        .where(metadata.Metadata.key == 'database_version')
                        .values({'value': str(migration_instance.number)})
                    )
                    last_migration_number = migration_instance.number
                    self.ap.logger.info(f'Migration {migration_instance.number} completed.')

            self.ap.logger.info(f'Successfully upgraded database to version {last_migration_number}.')

        await self.write_default_pipeline()

    async def create_tables(self):
        # create tables
        async with self.get_db_engine().connect() as conn:
            await conn.run_sync(self.meta.create_all)

            await conn.commit()

        # ======= write initial data =======

        # write initial metadata
        self.ap.logger.info('Creating initial metadata...')
        for item in metadata.initial_metadata:
            # check if the item exists
            result = await self.execute_async(
                sqlalchemy.select(metadata.Metadata).where(metadata.Metadata.key == item['key'])
            )
            row = result.first()
            if row is None:
                await self.execute_async(sqlalchemy.insert(metadata.Metadata).values(item))

    async def write_default_pipeline(self):
        # write default pipeline
        result = await self.execute_async(sqlalchemy.select(pipeline.LegacyPipeline))
        default_pipeline_uuid = None
        if result.first() is None:
            self.ap.logger.info('Creating default pipeline...')

            pipeline_config = json.loads(importutil.read_resource_file('templates/default-pipeline-config.json'))

            default_pipeline_uuid = str(uuid.uuid4())
            pipeline_data = {
                'uuid': default_pipeline_uuid,
                'for_version': self.ap.ver_mgr.get_current_version(),
                'stages': pipeline_service.default_stage_order,
                'is_default': True,
                'name': 'ChatPipeline',
                'description': 'Default pipeline, new bots will be bound to this pipeline | 默认提供的流水线，您配置的机器人将自动绑定到此流水线',
                'config': pipeline_config,
                'extensions_preferences': {},
            }

            await self.execute_async(sqlalchemy.insert(pipeline.LegacyPipeline).values(pipeline_data))

        # =================================

    async def execute_async(self, *args, **kwargs) -> sqlalchemy.engine.cursor.CursorResult:
        async with self.get_db_engine().connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result

    def get_db_engine(self) -> sqlalchemy_asyncio.AsyncEngine:
        return self.db.get_engine()

    def serialize_model(
        self, model: typing.Type[sqlalchemy.Base], data: sqlalchemy.Base, masked_columns: list[str] = []
    ) -> dict:
        return {
            column.name: getattr(data, column.name)
            if not isinstance(getattr(data, column.name), (datetime.datetime))
            else getattr(data, column.name).isoformat()
            for column in model.__table__.columns
            if column.name not in masked_columns
        }

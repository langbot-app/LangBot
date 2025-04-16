from __future__ import annotations

import asyncio
import datetime
import typing
import json
import uuid

import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy

from . import database, migration
from ..entity.persistence import base, user, model, pipeline, bot, plugin, metadata
from ..core import app
from .databases import sqlite
from ..utils import constants
from .migrations import dbm001_migrate_v3_config
from ..api.http.service import pipeline as pipeline_service


class PersistenceManager:
    """持久化模块管理器"""

    ap: app.Application

    db: database.BaseDatabaseManager
    """数据库管理器"""

    meta: sqlalchemy.MetaData

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.meta = base.Base.metadata

    async def initialize(self):

        self.ap.logger.info("Initializing database...")
        
        for manager in database.preregistered_managers:
            self.db = manager(self.ap)
            await self.db.initialize()

        await self.create_tables()

    async def create_tables(self):

        # create tables
        async with self.get_db_engine().connect() as conn:
            await conn.run_sync(self.meta.create_all)

            await conn.commit()

        # ======= write initial data =======

        # write initial metadata
        self.ap.logger.info("Creating initial metadata...")
        for item in metadata.initial_metadata:
            # check if the item exists
            result = await self.execute_async(
                sqlalchemy.select(metadata.Metadata).where(metadata.Metadata.key == item['key'])
            )
            row = result.first()
            if row is None:
                await self.execute_async(
                    sqlalchemy.insert(metadata.Metadata).values(item)
                )
        
        # write default pipeline
        result = await self.execute_async(
            sqlalchemy.select(pipeline.LegacyPipeline)
        )
        if result.first() is None:
            self.ap.logger.info("Creating default pipeline...")

            pipeline_config = json.load(open('templates/default-pipeline-config.json'))

            pipeline_data = {
                'uuid': str(uuid.uuid4()),
                'for_version': self.ap.ver_mgr.get_current_version(),
                'stages': pipeline_service.default_stage_order,
                'is_default': True,
                'name': 'Chat Pipeline',
                'description': '默认对话配置流水线',
                'config': pipeline_config,
            }

            await self.execute_async(
                sqlalchemy.insert(pipeline.LegacyPipeline).values(pipeline_data)
            )
        # =================================

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

                if migration_instance.number > database_version and migration_instance.number <= required_database_version:
                    await migration_instance.upgrade()
                    await self.execute_async(
                        sqlalchemy.update(metadata.Metadata).where(metadata.Metadata.key == 'database_version').values(
                            {
                                'value': str(migration_instance.number)
                            }
                        )
                    )
                    last_migration_number = migration_instance.number
                    self.ap.logger.info(f'Migration {migration_instance.number} completed.')
            
            self.ap.logger.info(f'Successfully upgraded database to version {last_migration_number}.')

    async def execute_async(
        self,
        *args,
        **kwargs
    ) -> sqlalchemy.engine.cursor.CursorResult:
        async with self.get_db_engine().connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result

    def get_db_engine(self) -> sqlalchemy_asyncio.AsyncEngine:
        return self.db.get_engine()
    
    def serialize_model(self, model: typing.Type[sqlalchemy.Base], data: sqlalchemy.Base) -> dict:
        return {
            column.name: getattr(data, column.name) if not isinstance(getattr(data, column.name), (datetime.datetime)) else getattr(data, column.name).isoformat()
            for column in model.__table__.columns
        }

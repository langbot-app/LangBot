from __future__ import annotations

import datetime
import typing


import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy

from . import database
from ..entity.persistence import base, model as persistence_model
from ..entity import persistence
from ..core import app
from ..utils import importutil
from . import databases

importutil.import_modules_in_pkg(databases)
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
        await self._run_alembic_migrations()

        await self.write_space_model_providers()

    async def create_tables(self):
        # create tables
        async with self.get_db_engine().connect() as conn:
            await conn.run_sync(self.meta.create_all)

            await conn.commit()

    async def write_space_model_providers(self):
        space_models_gateway_api_url = self.ap.instance_config.data.get('space', {}).get(
            'models_gateway_api_url', 'https://api.langbot.cloud/v1'
        )

        # write space model providers
        result = await self.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.requester == 'space-chat-completions'
            )
        )
        exists_space_chat_completions_model_provider = result.first()

        # api keys will be set/updated when the oauth callback
        if exists_space_chat_completions_model_provider is None:
            self.ap.logger.info('Creating space model providers...')
            space_chat_completions_model_provider = {
                'uuid': '00000000-0000-0000-0000-000000000000',
                'name': 'LangBot Models',
                'requester': 'space-chat-completions',
                'base_url': space_models_gateway_api_url,
                'api_keys': [],
            }

            await self.execute_async(
                sqlalchemy.insert(persistence_model.ModelProvider).values(space_chat_completions_model_provider)
            )
        else:
            if exists_space_chat_completions_model_provider.base_url != space_models_gateway_api_url:
                await self.execute_async(
                    sqlalchemy.update(persistence_model.ModelProvider)
                    .where(persistence_model.ModelProvider.uuid == exists_space_chat_completions_model_provider.uuid)
                    .values({'base_url': space_models_gateway_api_url})
                )

    # =================================

    async def _run_alembic_migrations(self):
        """Run Alembic migrations for supported 4.x databases."""
        from . import alembic_runner

        engine = self.get_db_engine()

        try:
            current_rev = await alembic_runner.get_alembic_current(engine)

            if current_rev is None:
                # First time: stamp baseline so Alembic knows existing schema is up-to-date
                self.ap.logger.info('Alembic: no revision found, stamping baseline...')
                await alembic_runner.run_alembic_stamp(engine, '0001_baseline')
                current_rev = '0001_baseline'

            # Upgrade to head
            await alembic_runner.run_alembic_upgrade(engine, 'head')
            self.ap.logger.info('Alembic migrations completed.')
        except Exception as e:
            self.ap.logger.error(f'Alembic migration failed: {e}', exc_info=True)
            raise

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

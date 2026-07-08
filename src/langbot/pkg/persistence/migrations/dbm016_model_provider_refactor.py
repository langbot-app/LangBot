import uuid as uuid_lib

import sqlalchemy
from .. import migration


@migration.migration_class(16)
class DBMigrateModelProviderRefactor(migration.DBMigration):
    """Refactor model structure: create providers from existing models and update references"""

    async def upgrade(self):
        """Upgrade"""
        # Step 1: Create model_providers table if not exists
        await self._create_providers_table()

        # Step 2: Migrate existing models to use providers
        await self._migrate_llm_models()
        await self._migrate_embedding_models()

        # Step 3: Remove deprecated columns
        await self._cleanup_columns()

    async def _create_providers_table(self):
        """Create model_providers table"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS model_providers (
                        uuid VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        requester VARCHAR(255) NOT NULL,
                        base_url VARCHAR(512) NOT NULL,
                        api_keys JSONB NOT NULL DEFAULT '[]',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS model_providers (
                        uuid VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        requester VARCHAR(255) NOT NULL,
                        base_url VARCHAR(512) NOT NULL,
                        api_keys JSON NOT NULL DEFAULT '[]',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )

    async def _migrate_llm_models(self):
        """Migrate LLM models to use providers"""
        llm_columns = await self._get_columns('llm_models')

        # Add provider_uuid column if not exists
        if 'provider_uuid' not in llm_columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE llm_models ADD COLUMN provider_uuid VARCHAR(255)')
            )

        # Add prefered_ranking column if not exists
        if 'prefered_ranking' not in llm_columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE llm_models ADD COLUMN prefered_ranking INTEGER NOT NULL DEFAULT 0')
            )

        # Only migrate if old columns exist
        if 'requester' not in llm_columns:
            return

        # Get all LLM models with old structure
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, name, requester, requester_config, api_keys FROM llm_models')
        )
        models = result.fetchall()

        # Create providers and update models
        provider_cache = {}  # (requester, base_url, api_keys_str) -> provider_uuid

        for model in models:
            model_uuid, model_name, requester, requester_config, api_keys = model

            # Extract base_url from requester_config
            base_url = ''
            if requester_config:
                if isinstance(requester_config, str):
                    import json

                    requester_config = json.loads(requester_config)
                base_url = requester_config.get('base_url', '') or requester_config.get('base-url', '')

            # Parse api_keys if it's a string
            if isinstance(api_keys, str):
                import json

                try:
                    api_keys = json.loads(api_keys)
                except Exception:
                    api_keys = []
            if not api_keys:
                api_keys = []

            # Create cache key
            api_keys_str = str(sorted(api_keys)) if api_keys else '[]'
            cache_key = (requester, base_url, api_keys_str)

            if cache_key in provider_cache:
                provider_uuid = provider_cache[cache_key]
            else:
                # Create new provider
                provider_uuid = str(uuid_lib.uuid4())
                provider_name = f'{requester}'
                if base_url:
                    # Extract domain for name
                    try:
                        from urllib.parse import urlparse

                        parsed = urlparse(base_url)
                        provider_name = parsed.netloc or requester
                    except Exception:
                        pass

                import json

                api_keys_json = json.dumps(api_keys) if api_keys else '[]'

                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text("""
                        INSERT INTO model_providers (uuid, name, requester, base_url, api_keys)
                        VALUES (:uuid, :name, :requester, :base_url, :api_keys)
                    """),
                    {
                        'uuid': provider_uuid,
                        'name': provider_name,
                        'requester': requester,
                        'base_url': base_url,
                        'api_keys': api_keys_json,
                    },
                )
                provider_cache[cache_key] = provider_uuid

            # Update model with provider_uuid
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('UPDATE llm_models SET provider_uuid = :provider_uuid WHERE uuid = :uuid'),
                {'provider_uuid': provider_uuid, 'uuid': model_uuid},
            )

    async def _migrate_embedding_models(self):
        """Migrate embedding models to use providers"""
        embedding_columns = await self._get_columns('embedding_models')

        # Add provider_uuid column if not exists
        if 'provider_uuid' not in embedding_columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE embedding_models ADD COLUMN provider_uuid VARCHAR(255)')
            )

        # Add prefered_ranking column if not exists
        if 'prefered_ranking' not in embedding_columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE embedding_models ADD COLUMN prefered_ranking INTEGER NOT NULL DEFAULT 0')
            )

        # Only migrate if old columns exist
        if 'requester' not in embedding_columns:
            return

        # Get all embedding models with old structure
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, name, requester, requester_config, api_keys FROM embedding_models')
        )
        models = result.fetchall()

        # Get existing providers
        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, requester, base_url, api_keys FROM model_providers')
        )
        existing_providers = provider_result.fetchall()

        provider_cache = {}
        for p in existing_providers:
            p_uuid, p_requester, p_base_url, p_api_keys = p
            api_keys_str = str(sorted(p_api_keys)) if p_api_keys else '[]'
            provider_cache[(p_requester, p_base_url, api_keys_str)] = p_uuid

        for model in models:
            model_uuid, model_name, requester, requester_config, api_keys = model

            base_url = ''
            if requester_config:
                if isinstance(requester_config, str):
                    import json

                    requester_config = json.loads(requester_config)
                base_url = requester_config.get('base_url', '') or requester_config.get('base-url', '')

            # Parse api_keys if it's a string
            if isinstance(api_keys, str):
                import json

                try:
                    api_keys = json.loads(api_keys)
                except Exception:
                    api_keys = []
            if not api_keys:
                api_keys = []

            api_keys_str = str(sorted(api_keys)) if api_keys else '[]'
            cache_key = (requester, base_url, api_keys_str)

            if cache_key in provider_cache:
                provider_uuid = provider_cache[cache_key]
            else:
                provider_uuid = str(uuid_lib.uuid4())
                provider_name = f'{requester}'
                if base_url:
                    try:
                        from urllib.parse import urlparse

                        parsed = urlparse(base_url)
                        provider_name = parsed.netloc or requester
                    except Exception:
                        pass

                import json

                api_keys_json = json.dumps(api_keys) if api_keys else '[]'

                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text("""
                        INSERT INTO model_providers (uuid, name, requester, base_url, api_keys)
                        VALUES (:uuid, :name, :requester, :base_url, :api_keys)
                    """),
                    {
                        'uuid': provider_uuid,
                        'name': provider_name,
                        'requester': requester,
                        'base_url': base_url,
                        'api_keys': api_keys_json,
                    },
                )
                provider_cache[cache_key] = provider_uuid

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('UPDATE embedding_models SET provider_uuid = :provider_uuid WHERE uuid = :uuid'),
                {'provider_uuid': provider_uuid, 'uuid': model_uuid},
            )

    async def _cleanup_columns(self):
        """Remove deprecated columns from model tables"""

        llm_columns = await self._get_columns('llm_models')
        deprecated_llm_cols = ['requester', 'requester_config', 'api_keys', 'description', 'source', 'space_model_id']
        for col in deprecated_llm_cols:
            if col in llm_columns:
                if self.ap.persistence_mgr.db.name == 'postgresql':
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.text(f'ALTER TABLE llm_models DROP COLUMN IF EXISTS {col}')
                    )
                else:
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.text(f'ALTER TABLE llm_models DROP COLUMN {col}')
                    )

        embedding_columns = await self._get_columns('embedding_models')
        deprecated_embedding_cols = [
            'requester',
            'requester_config',
            'api_keys',
            'description',
            'source',
            'space_model_id',
        ]
        for col in deprecated_embedding_cols:
            if col in embedding_columns:
                if self.ap.persistence_mgr.db.name == 'postgresql':
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.text(f'ALTER TABLE embedding_models DROP COLUMN IF EXISTS {col}')
                    )
                else:
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.text(f'ALTER TABLE embedding_models DROP COLUMN {col}')
                    )

    async def _get_columns(self, table_name: str) -> list:
        """Get column names for a table"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';"
                )
            )
            all_result = result.fetchall()
            return [row[0] for row in all_result]
        else:
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
            all_result = result.fetchall()
            return [row[1] for row in all_result]

    async def downgrade(self):
        """Downgrade"""
        pass

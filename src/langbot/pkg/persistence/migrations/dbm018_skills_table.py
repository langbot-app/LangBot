import sqlalchemy
from .. import migration


@migration.migration_class(18)
class DBMigrateSkillsTable(migration.DBMigration):
    """Create skills and skill_pipeline_bindings tables"""

    async def upgrade(self):
        """Upgrade"""
        await self._create_skills_table()
        await self._create_skill_pipeline_bindings_table()

    async def _create_skills_table(self):
        """Create skills table"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS skills (
                        uuid VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(64) NOT NULL UNIQUE,
                        description VARCHAR(1024) NOT NULL,
                        instructions TEXT NOT NULL,
                        type VARCHAR(32) NOT NULL DEFAULT 'skill',
                        requires_tools JSONB NOT NULL DEFAULT '[]',
                        requires_kbs JSONB NOT NULL DEFAULT '[]',
                        requires_skills JSONB NOT NULL DEFAULT '[]',
                        auto_activate BOOLEAN NOT NULL DEFAULT TRUE,
                        trigger_keywords JSONB NOT NULL DEFAULT '[]',
                        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
                        author VARCHAR(255),
                        version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
                        tags JSONB NOT NULL DEFAULT '[]',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS skills (
                        uuid VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(64) NOT NULL UNIQUE,
                        description VARCHAR(1024) NOT NULL,
                        instructions TEXT NOT NULL,
                        type VARCHAR(32) NOT NULL DEFAULT 'skill',
                        requires_tools JSON NOT NULL DEFAULT '[]',
                        requires_kbs JSON NOT NULL DEFAULT '[]',
                        requires_skills JSON NOT NULL DEFAULT '[]',
                        auto_activate BOOLEAN NOT NULL DEFAULT 1,
                        trigger_keywords JSON NOT NULL DEFAULT '[]',
                        is_enabled BOOLEAN NOT NULL DEFAULT 1,
                        is_builtin BOOLEAN NOT NULL DEFAULT 0,
                        author VARCHAR(255),
                        version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
                        tags JSON NOT NULL DEFAULT '[]',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )

    async def _create_skill_pipeline_bindings_table(self):
        """Create skill_pipeline_bindings table"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS skill_pipeline_bindings (
                        id SERIAL PRIMARY KEY,
                        skill_uuid VARCHAR(255) NOT NULL REFERENCES skills(uuid) ON DELETE CASCADE,
                        pipeline_uuid VARCHAR(255) NOT NULL REFERENCES legacy_pipelines(uuid) ON DELETE CASCADE,
                        priority INTEGER NOT NULL DEFAULT 0,
                        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(skill_uuid, pipeline_uuid)
                    )
                """)
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS skill_pipeline_bindings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        skill_uuid VARCHAR(255) NOT NULL,
                        pipeline_uuid VARCHAR(255) NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 0,
                        is_enabled BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (skill_uuid) REFERENCES skills(uuid) ON DELETE CASCADE,
                        FOREIGN KEY (pipeline_uuid) REFERENCES legacy_pipelines(uuid) ON DELETE CASCADE,
                        UNIQUE(skill_uuid, pipeline_uuid)
                    )
                """)
            )

    async def downgrade(self):
        """Downgrade"""
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE IF EXISTS skill_pipeline_bindings'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE IF EXISTS skills'))

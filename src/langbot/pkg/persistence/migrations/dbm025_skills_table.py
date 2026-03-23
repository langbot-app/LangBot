import sqlalchemy
from .. import migration


@migration.migration_class(25)
class DBMigrateSkillsTable(migration.DBMigration):
    """Create skills registry table.

    Skills table is a registry — only stores LangBot-local governance info.
    Package metadata (description, author, etc.) lives in SKILL.md frontmatter.
    """

    async def upgrade(self):
        """Upgrade"""
        await self._create_skills_table()

    async def _create_skills_table(self):
        """Create skills table"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS skills (
                        uuid VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(64) NOT NULL UNIQUE,
                        package_root VARCHAR(1024) NOT NULL DEFAULT '',
                        entry_file VARCHAR(255) NOT NULL DEFAULT 'SKILL.md',
                        sandbox_timeout_sec INTEGER NOT NULL DEFAULT 120,
                        sandbox_network BOOLEAN NOT NULL DEFAULT FALSE,
                        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
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
                        package_root VARCHAR(1024) NOT NULL DEFAULT '',
                        entry_file VARCHAR(255) NOT NULL DEFAULT 'SKILL.md',
                        sandbox_timeout_sec INTEGER NOT NULL DEFAULT 120,
                        sandbox_network BOOLEAN NOT NULL DEFAULT 0,
                        is_enabled BOOLEAN NOT NULL DEFAULT 1,
                        is_builtin BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )

    async def downgrade(self):
        """Downgrade"""
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE IF EXISTS skills'))

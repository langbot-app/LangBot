import sqlalchemy
from .. import migration


@migration.migration_class(14)
class DBMigrateSpaceAccountSupport(migration.DBMigration):
    """Add Space account support fields to users table"""

    async def upgrade(self):
        """Upgrade"""
        # Get all column names from the users table
        columns = []

        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';")
            )
            all_result = result.fetchall()
            columns = [row[0] for row in all_result]
        else:
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text('PRAGMA table_info(users);'))
            all_result = result.fetchall()
            columns = [row[1] for row in all_result]

        # Add account_type column
        if 'account_type' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text("ALTER TABLE users ADD COLUMN account_type VARCHAR(32) DEFAULT 'local' NOT NULL")
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text("ALTER TABLE users ADD COLUMN account_type VARCHAR(32) DEFAULT 'local' NOT NULL")
                )

        # Add space_account_uuid column
        if 'space_account_uuid' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_account_uuid VARCHAR(255)')
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_account_uuid VARCHAR(255)')
                )

        # Add space_access_token column
        if 'space_access_token' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_access_token TEXT')
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_access_token TEXT')
                )

        # Add space_refresh_token column
        if 'space_refresh_token' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_refresh_token TEXT')
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_refresh_token TEXT')
                )

        # Add space_access_token_expires_at column
        if 'space_access_token_expires_at' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_access_token_expires_at TIMESTAMP')
                )

            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_access_token_expires_at DATETIME')
                )

        # Add space_api_key column
        if 'space_api_key' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_api_key VARCHAR(255)')
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE users ADD COLUMN space_api_key VARCHAR(255)')
                )

    async def downgrade(self):
        """Downgrade"""
        pass

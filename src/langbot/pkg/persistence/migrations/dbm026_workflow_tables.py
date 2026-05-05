"""Add workflow tables and update bot binding fields"""
import sqlalchemy
from .. import migration


@migration.migration_class(26)
class DBMigrateWorkflowTables(migration.DBMigration):
    """Add workflow tables and update bot binding fields"""

    async def upgrade(self):
        # Create workflows table
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS workflows (
                uuid VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                emoji VARCHAR(10) DEFAULT '🔄',
                version INTEGER NOT NULL DEFAULT 1,
                is_enabled BOOLEAN NOT NULL DEFAULT 1,
                definition JSON NOT NULL DEFAULT '{}',
                global_config JSON NOT NULL DEFAULT '{}',
                extensions_preferences JSON NOT NULL DEFAULT '{"enable_all_plugins": true, "enable_all_mcp_servers": true, "plugins": [], "mcp_servers": []}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create workflow_versions table
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS workflow_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_uuid VARCHAR(255) NOT NULL,
                version INTEGER NOT NULL,
                definition JSON NOT NULL,
                global_config JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(255),
                UNIQUE(workflow_uuid, version)
            )
        """))

        # Create workflow_triggers table
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS workflow_triggers (
                uuid VARCHAR(255) PRIMARY KEY,
                workflow_uuid VARCHAR(255) NOT NULL,
                type VARCHAR(50) NOT NULL,
                config JSON NOT NULL DEFAULT '{}',
                is_enabled BOOLEAN NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create workflow_executions table
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS workflow_executions (
                uuid VARCHAR(255) PRIMARY KEY,
                workflow_uuid VARCHAR(255) NOT NULL,
                workflow_version INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL,
                trigger_type VARCHAR(50),
                trigger_data JSON,
                variables JSON,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create workflow_node_executions table
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS workflow_node_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_uuid VARCHAR(255) NOT NULL,
                node_id VARCHAR(100) NOT NULL,
                node_type VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL,
                inputs JSON,
                outputs JSON,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0
            )
        """))

        # Create workflow_scheduled_jobs table
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS workflow_scheduled_jobs (
                uuid VARCHAR(255) PRIMARY KEY,
                trigger_uuid VARCHAR(255) NOT NULL,
                cron_expression VARCHAR(100),
                next_run_time TIMESTAMP,
                last_run_time TIMESTAMP,
                is_enabled BOOLEAN NOT NULL DEFAULT 1
            )
        """))

        # Create indexes
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
            "CREATE INDEX IF NOT EXISTS idx_workflow_versions_uuid ON workflow_versions(workflow_uuid)"
        ))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
            "CREATE INDEX IF NOT EXISTS idx_workflow_triggers_uuid ON workflow_triggers(workflow_uuid)"
        ))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
            "CREATE INDEX IF NOT EXISTS idx_workflow_executions_uuid ON workflow_executions(workflow_uuid)"
        ))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
            "CREATE INDEX IF NOT EXISTS idx_workflow_node_executions_uuid ON workflow_node_executions(execution_uuid)"
        ))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
            "CREATE INDEX IF NOT EXISTS idx_workflow_scheduled_jobs_trigger ON workflow_scheduled_jobs(trigger_uuid)"
        ))

        # Update bots table: add binding_type column (default to 'pipeline' for backward compatibility)
        # Check if column exists first (SQLite doesn't support IF NOT EXISTS for columns)
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT binding_type FROM bots LIMIT 1")
            )
        except Exception:
            # Column doesn't exist, add it
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
                "ALTER TABLE bots ADD COLUMN binding_type VARCHAR(20) NOT NULL DEFAULT 'pipeline'"
            ))

    async def downgrade(self):
        # Drop tables in reverse order
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("DROP TABLE IF EXISTS workflow_scheduled_jobs"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("DROP TABLE IF EXISTS workflow_node_executions"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("DROP TABLE IF EXISTS workflow_executions"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("DROP TABLE IF EXISTS workflow_triggers"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("DROP TABLE IF EXISTS workflow_versions"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("DROP TABLE IF EXISTS workflows"))
        
        # Remove binding_type column from bots (SQLite doesn't support DROP COLUMN directly)
        # This would need a table recreation in SQLite, so we'll skip it in downgrade

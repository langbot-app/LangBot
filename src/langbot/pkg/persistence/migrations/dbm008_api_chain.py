"""Database migration for API Chain feature"""

from sqlalchemy import text


async def migrate(ap):
    """Add API chain tables"""

    # Create api_chains table
    await ap.persistence_mgr.execute_async(
        text("""
        CREATE TABLE IF NOT EXISTS api_chains (
            uuid VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description VARCHAR(512),
            chain_config JSON NOT NULL,
            health_check_interval INTEGER NOT NULL DEFAULT 300,
            health_check_enabled BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    )

    # Create api_chain_status table
    await ap.persistence_mgr.execute_async(
        text("""
        CREATE TABLE IF NOT EXISTS api_chain_status (
            uuid VARCHAR(255) PRIMARY KEY,
            chain_uuid VARCHAR(255) NOT NULL,
            provider_uuid VARCHAR(255) NOT NULL,
            is_healthy BOOLEAN NOT NULL DEFAULT 1,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_failure_time DATETIME,
            last_success_time DATETIME,
            last_health_check_time DATETIME,
            last_error_message VARCHAR(1024),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_chain_uuid (chain_uuid),
            INDEX idx_provider_uuid (provider_uuid)
        )
        """)
    )

    ap.logger.info('API Chain tables created successfully')

import sqlalchemy
from sqlalchemy import JSON, Integer, String, DateTime, Boolean
from .base import Base


class APIChain(Base):
    """API Chain - manages multiple API providers with priority and failover"""

    __tablename__ = 'api_chains'

    uuid = sqlalchemy.Column(String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(String(255), nullable=False)
    description = sqlalchemy.Column(String(512), nullable=True)
    
    # Chain configuration
    chain_config = sqlalchemy.Column(JSON, nullable=False, default=list)
    """
    List of API chain items:
    [
        {
            "provider_uuid": "xxx",
            "priority": 1,              // provider priority in the chain
            "is_aggregated": false,
            "max_retries": 3,
            "timeout_ms": 30000,
            "model_configs": [          // optional: per-model priority config
                {
                    "model_name": "gpt-4o",   // model name (as in LLMModel.name)
                    "priority": 1,             // model priority within this provider
                    "api_key_indices": [        // optional: per-API-key priority
                        {"index": 0, "priority": 1},
                        {"index": 1, "priority": 2}
                    ]
                }
            ]
        },
        ...
    ]
    If model_configs is empty/absent, the chain uses the query's original model
    with round-robin API key rotation. If api_key_indices is empty/absent for a
    model config, round-robin rotation is used for that model.
    """
    
    # Health check configuration
    health_check_interval = sqlalchemy.Column(Integer, nullable=False, default=300)
    """Health check interval in seconds for failed APIs"""
    
    health_check_enabled = sqlalchemy.Column(Boolean, nullable=False, default=True)
    """Whether to enable automatic health check for failed APIs"""
    
    # Metadata
    created_at = sqlalchemy.Column(DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class APIChainStatus(Base):
    """API Chain Status - tracks the health status of APIs in chains"""

    __tablename__ = 'api_chain_status'

    uuid = sqlalchemy.Column(String(255), primary_key=True, unique=True)
    chain_uuid = sqlalchemy.Column(String(255), nullable=False, index=True)
    provider_uuid = sqlalchemy.Column(String(255), nullable=False, index=True)
    
    # Granularity: model-level and API-key-level tracking
    model_name = sqlalchemy.Column(String(255), nullable=True, index=True)
    """Model name (from LLMModel.name); NULL means provider-level status"""

    api_key_index = sqlalchemy.Column(Integer, nullable=True)
    """Index into the provider's api_keys list; NULL means all/round-robin"""
    
    # Status tracking
    is_healthy = sqlalchemy.Column(Boolean, nullable=False, default=True)
    failure_count = sqlalchemy.Column(Integer, nullable=False, default=0)
    last_failure_time = sqlalchemy.Column(DateTime, nullable=True)
    last_success_time = sqlalchemy.Column(DateTime, nullable=True)
    last_health_check_time = sqlalchemy.Column(DateTime, nullable=True)
    
    # Error information
    last_error_message = sqlalchemy.Column(String(1024), nullable=True)
    
    # Metadata
    created_at = sqlalchemy.Column(DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

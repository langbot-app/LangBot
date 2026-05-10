"""E2E test configuration factory.

Generates minimal config.yaml for testing LangBot startup without external dependencies.
"""

from __future__ import annotations

import yaml
from pathlib import Path


def create_minimal_config(tmpdir: Path, port: int = 15300) -> Path:
    """Create minimal config.yaml for E2E testing.

    Uses embedded databases (SQLite, Chroma) to avoid external dependencies.
    Config is created at tmpdir/data/config.yaml (LangBot expects this location).
    """
    # LangBot expects config at data/config.yaml
    data_dir = tmpdir / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    config = {
        'admins': [],
        'api': {
            'port': port,
            'webhook_prefix': f'http://127.0.0.1:{port}',
            'extra_webhook_prefix': '',
        },
        'command': {
            'enable': True,
            'prefix': ['!', '!'],
            'privilege': {},
        },
        'concurrency': {
            'pipeline': 20,
            'session': 1,
        },
        'proxy': {
            'http': '',
            'https': '',
        },
        'system': {
            'instance_id': '',
            'edition': 'community',
            'recovery_key': '',
            'allow_modify_login_info': True,
            'disabled_adapters': [],
            'limitation': {
                'max_bots': -1,
                'max_pipelines': -1,
                'max_extensions': -1,
            },
            'task_retention': {
                'completed_limit': 200,
            },
            'jwt': {
                'expire': 604800,
                'secret': 'e2e-test-secret-key',
            },
        },
        'database': {
            'use': 'sqlite',
            'sqlite': {
                'path': str(tmpdir / 'data' / 'langbot.db'),
            },
            'postgresql': {
                'host': '127.0.0.1',
                'port': 5432,
                'user': 'postgres',
                'password': 'postgres',
                'database': 'postgres',
            },
        },
        'vdb': {
            'use': 'chroma',  # Chroma is embedded, no external dependency
            'chroma': {
                'path': str(tmpdir / 'chroma'),
            },
            'qdrant': {
                'url': '',
                'host': 'localhost',
                'port': 6333,
                'api_key': '',
            },
            'seekdb': {
                'mode': 'embedded',
                'path': str(tmpdir / 'seekdb'),
                'database': 'langbot',
                'host': 'localhost',
                'port': 2881,
                'user': 'root',
                'password': '',
                'tenant': '',
            },
            'milvus': {
                'uri': 'http://127.0.0.1:19530',
                'token': '',
                'db_name': '',
            },
            'pgvector': {
                'host': '127.0.0.1',
                'port': 5433,
                'database': 'langbot',
                'user': 'postgres',
                'password': 'postgres',
            },
        },
        'storage': {
            'use': 'local',
            'cleanup': {
                'enabled': False,  # Disable cleanup for tests
                'check_interval_hours': 1,
                'uploaded_file_retention_days': 7,
                'log_retention_days': 3,
            },
            'local': {
                'path': str(tmpdir / 'storage'),
            },
            's3': {
                'endpoint_url': '',
                'access_key_id': '',
                'secret_access_key': '',
                'region': 'us-east-1',
                'bucket': 'langbot-storage',
            },
        },
        'plugin': {
            'enable': False,  # Disable plugin system for minimal startup
            'runtime_ws_url': '',
            'enable_marketplace': False,
            'display_plugin_debug_url': '',
            'binary_storage': {
                'max_value_bytes': 10485760,
            },
        },
        'monitoring': {
            'auto_cleanup': {
                'enabled': False,  # Disable cleanup for tests
                'retention_days': 30,
                'check_interval_hours': 1,
                'delete_batch_size': 1000,
            },
        },
        'space': {
            'url': 'https://space.langbot.app',
            'models_gateway_api_url': 'https://api.langbot.cloud/v1',
            'oauth_authorize_url': 'https://space.langbot.app/auth/authorize',
            'disable_models_service': True,  # Disable external services
            'disable_telemetry': True,  # Disable telemetry for tests
        },
        'provider': {},  # Empty providers - minimal startup
        'llm': [],  # Empty LLM models
    }

    # Ensure data directory exists (LangBot expects config at data/config.yaml)
    data_dir = tmpdir / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    # Write config to data/config.yaml (LangBot's expected location)
    config_path = data_dir / 'config.yaml'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False)

    return config_path


def create_test_directories(tmpdir: Path) -> dict[str, Path]:
    """Create necessary directories for LangBot testing."""
    directories = {
        'data': tmpdir / 'data',
        'logs': tmpdir / 'logs',
        'storage': tmpdir / 'storage',
        'chroma': tmpdir / 'chroma',
    }

    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)

    return directories
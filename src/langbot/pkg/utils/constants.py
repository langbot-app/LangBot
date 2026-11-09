import langbot

semantic_version = f'v{langbot.__version__}'

debug_mode = False

edition = 'community'

instance_id = ''

instance_create_ts = 0
"""Unix timestamp (seconds) of when this instance was first created.

Sourced from ``data/labels/instance_id.json``. Backfilled to the current
time for instances created before this field existed, so it is always a
positive value once load_config has run.
"""

WEBSOCKET_PROXY_BOT_UUID = 'websocket-proxy-bot'
"""Reserved bot UUID of the per-Workspace WebSocket debug proxy.

The proxy is an in-memory ``RuntimeBot`` created by ``PlatformManager`` for
pipeline debug chat / ``run_pipeline``; it never has a row in the ``bots``
table, so its existence must be checked against the runtime, not the database.
"""

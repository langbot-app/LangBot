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


# 流水线"会话测试"用的内置 WebSocket 代理 Bot。它是内存里的 RuntimeBot，
# 从不落 bots 表，因此任何"按 uuid 查库"的校验都要放行它。
WEBSOCKET_PROXY_BOT_UUID = 'websocket-proxy-bot'

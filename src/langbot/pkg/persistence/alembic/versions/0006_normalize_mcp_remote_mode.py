"""normalize mcp_servers transport mode to local/remote

The MCP transport selection for servers LangBot connects to was simplified
from three persisted modes (``stdio`` / ``sse`` / ``http``) down to two:
``stdio`` (local, Box-sandboxed) and ``remote`` (the runtime auto-detects
Streamable HTTP vs. legacy SSE from the URL). This migration rewrites any
existing ``sse`` / ``http`` rows to ``remote`` so the stored value matches the
new two-option UI. The connection args (url / headers / timeout /
ssereadtimeout) live in ``extra_args`` and are left untouched — the
auto-detecting remote transport consumes them regardless.

Revision ID: 0006_normalize_mcp_remote_mode
Revises: 0005_add_llm_context_length
Create Date: 2026-06-21
"""

import sqlalchemy as sa
from alembic import op

revision = '0006_normalize_mcp_remote_mode'
down_revision = '0005_add_llm_context_length'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent data migration: collapse legacy remote transports into the
    # unified ``remote`` mode. Guard against the table being absent (truly empty
    # DB migrated before create_all()).
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'mcp_servers' not in inspector.get_table_names():
        return
    conn.execute(sa.text("UPDATE mcp_servers SET mode = 'remote' WHERE mode IN ('sse', 'http')"))


def downgrade() -> None:
    # The legacy distinction between ``sse`` and ``http`` cannot be recovered
    # from ``remote`` alone (the transport is auto-detected at runtime, not
    # stored). Map everything that is not ``stdio`` back to ``http`` as a
    # best-effort reversal — both legacy modes still route correctly in the
    # backend lifecycle dispatch.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'mcp_servers' not in inspector.get_table_names():
        return
    conn.execute(sa.text("UPDATE mcp_servers SET mode = 'http' WHERE mode = 'remote'"))

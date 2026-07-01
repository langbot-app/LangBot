"""merge mcp resource and agent product migration heads

Revision ID: 0010_merge_mcp_resource_agent_heads
Revises: 0008_mcp_resource_prefs, 0009_migrate_routing_to_event_bindings
Create Date: 2026-06-30
"""

revision = '0010_merge_mcp_resource_agent_heads'
down_revision = ('0008_mcp_resource_prefs', '0009_migrate_routing_to_event_bindings')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

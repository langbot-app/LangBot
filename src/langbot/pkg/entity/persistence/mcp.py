import sqlalchemy

from .base import Base


class MCPServer(Base):
    __tablename__ = 'mcp_servers'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    enable = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    mode = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)  # stdio, remote (legacy: sse, http)
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    # Markdown documentation captured from LangBot Space at install time so the
    # detail page can show docs even when the server is offline / has no tools.
    # Empty string for manually-created servers that have no marketplace README.
    readme = sqlalchemy.Column(sqlalchemy.Text, nullable=False, server_default='', default='')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'name', name='uq_mcp_servers_workspace_name'),
        sqlalchemy.Index('ix_mcp_servers_workspace_enable', 'workspace_uuid', 'enable'),
    )

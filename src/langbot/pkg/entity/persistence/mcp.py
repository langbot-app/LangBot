import sqlalchemy

from .base import Base


class MCPServer(Base):
    __tablename__ = 'mcp_servers'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    enable = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    mode = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)  # stdio, sse, http
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

import sqlalchemy

from .base import Base


class PluginSetting(Base):
    """Plugin setting"""

    __tablename__ = 'plugin_settings'

    plugin_author = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    plugin_name = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    install_source = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='github')
    install_info = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

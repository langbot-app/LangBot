import sqlalchemy

from .base import Base


class Bot(Base):
    """机器人"""
    __tablename__ = 'bots'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    adapter = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    adapter_config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    enable = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now())

import sqlalchemy

from .base import Base


class Agent(Base):
    """Product-level Agent processor."""

    __tablename__ = 'agents'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='')
    emoji = sqlalchemy.Column(sqlalchemy.String(10), nullable=True, default='🤖')
    kind = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='agent')
    component_ref = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    supported_event_patterns = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=['*'])
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

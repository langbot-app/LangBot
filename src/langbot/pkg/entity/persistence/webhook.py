import sqlalchemy

from .base import Base


class Webhook(Base):
    """Webhook for pushing bot events to external systems"""

    __tablename__ = 'webhooks'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    url = sqlalchemy.Column(sqlalchemy.String(1024), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(512), nullable=True, default='')
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

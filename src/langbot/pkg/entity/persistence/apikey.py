import sqlalchemy

from .base import Base


class ApiKey(Base):
    """API Key for external service authentication"""

    __tablename__ = 'api_keys'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    key = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String(512), nullable=True, default='')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

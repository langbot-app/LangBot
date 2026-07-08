import sqlalchemy

from .base import Base


class User(Base):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)

    # Account type: 'local' (default) or 'space'
    account_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, server_default='local')

    # Space account fields (nullable, only used when account_type='space')
    space_account_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    space_access_token = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    space_refresh_token = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    space_access_token_expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    space_api_key = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

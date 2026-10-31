import sqlalchemy

from .base import Base


class BinaryStorage(Base):
    """Current for plugin use only"""

    __tablename__ = 'binary_storages'

    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        primary_key=True,
    )
    unique_key = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    key = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    owner_type = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    owner = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    value = sqlalchemy.Column(sqlalchemy.LargeBinary, nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.Index(
            'ix_binary_storages_workspace_owner',
            'workspace_uuid',
            'owner_type',
            'owner',
        ),
    )

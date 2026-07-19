import sqlalchemy

from .base import Base
from ...utils import constants


initial_metadata = [
    {
        'key': 'database_version',
        'value': str(constants.required_database_version),
    },
]


class Metadata(Base):
    """Database metadata"""

    __tablename__ = 'metadata'

    key = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String(255))


class WorkspaceMetadata(Base):
    """Metadata owned by one workspace rather than by the LangBot instance."""

    __tablename__ = 'workspace_metadata'

    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        primary_key=True,
    )
    key = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String(255))

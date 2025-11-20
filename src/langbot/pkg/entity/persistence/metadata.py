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

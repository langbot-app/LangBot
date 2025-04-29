import sqlalchemy

from .base import Base


initial_metadata = [
    {
        'key': 'database_version',
        'value': '0',
    },
]


class Metadata(Base):
    """数据库元数据"""

    __tablename__ = 'metadata'

    key = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String(255))

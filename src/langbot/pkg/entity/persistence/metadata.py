import sqlalchemy

from .base import Base


class Metadata(Base):
    """Database metadata"""

    __tablename__ = 'metadata'

    key = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String(255))

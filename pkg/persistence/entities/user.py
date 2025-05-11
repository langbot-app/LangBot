import sqlalchemy

from .base import Base


class User(Base):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)

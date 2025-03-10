import sqlalchemy.orm
import pydantic


class Base(sqlalchemy.orm.DeclarativeBase):
    pass

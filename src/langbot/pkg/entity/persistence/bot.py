import sqlalchemy

from .base import Base


class BotAdmin(Base):
    """Bot admin — a launcher that has admin privilege for a specific bot's commands"""

    __tablename__ = 'bot_admins'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    launcher_type = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    launcher_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

    __table_args__ = (sqlalchemy.UniqueConstraint('bot_uuid', 'launcher_type', 'launcher_id', name='uq_bot_admin'),)


class Bot(Base):
    """Bot"""

    __tablename__ = 'bots'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    adapter = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    adapter_config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    enable = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    use_pipeline_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    use_pipeline_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    pipeline_routing_rules = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

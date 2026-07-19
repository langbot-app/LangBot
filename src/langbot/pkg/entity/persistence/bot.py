import sqlalchemy

from .base import Base


class BotAdmin(Base):
    """Bot admin — a launcher that has admin privilege for a specific bot's commands"""

    __tablename__ = 'bot_admins'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    launcher_type = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    launcher_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'workspace_uuid',
            'bot_uuid',
            'launcher_type',
            'launcher_id',
            name='uq_bot_admin',
        ),
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'bot_uuid'],
            ['bots.workspace_uuid', 'bots.uuid'],
            name='fk_bot_admins_workspace_bot',
            ondelete='CASCADE',
        ),
    )


class Bot(Base):
    """Bot"""

    __tablename__ = 'bots'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
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

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'uuid', name='uq_bots_workspace_uuid'),
        sqlalchemy.Index('ix_bots_workspace_name', 'workspace_uuid', 'name'),
    )

import sqlalchemy

from .base import Base


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
    
    # New unified binding fields
    # binding_type: 'pipeline' or 'workflow'
    binding_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, server_default='pipeline')
    # binding_uuid: UUID of the bound Pipeline or Workflow
    binding_uuid = sqlalchemy.Column(sqlalchemy.String(64), nullable=True)
    
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

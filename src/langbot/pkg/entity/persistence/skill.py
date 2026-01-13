import sqlalchemy

from .base import Base


class Skill(Base):
    """Skill entity for storing skill definitions"""

    __tablename__ = 'skills'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String(1024), nullable=False)
    instructions = sqlalchemy.Column(sqlalchemy.Text, nullable=False)

    # Type: "skill" (single skill) | "workflow" (workflow with steps)
    type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='skill')

    # Dependencies configuration
    requires_tools = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    requires_kbs = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    requires_skills = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])

    # Trigger configuration
    auto_activate = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    trigger_keywords = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])

    # Status
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    is_builtin = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    # Metadata
    author = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    version = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='1.0.0')
    tags = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class SkillPipelineBinding(Base):
    """Binding relationship between Skill and Pipeline"""

    __tablename__ = 'skill_pipeline_bindings'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    skill_uuid = sqlalchemy.Column(sqlalchemy.String(255), sqlalchemy.ForeignKey('skills.uuid'), nullable=False)
    pipeline_uuid = sqlalchemy.Column(
        sqlalchemy.String(255), sqlalchemy.ForeignKey('legacy_pipelines.uuid'), nullable=False
    )
    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

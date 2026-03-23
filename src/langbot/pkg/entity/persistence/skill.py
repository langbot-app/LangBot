import sqlalchemy

from .base import Base


class Skill(Base):
    """Skill registry entry.

    Only stores LangBot-local registration and governance info.
    Package metadata (display_name, description, author, etc.) lives in SKILL.md frontmatter.
    """

    __tablename__ = 'skills'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, unique=True)

    # Package location
    package_root = sqlalchemy.Column(sqlalchemy.String(1024), nullable=False, default='')
    entry_file = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, default='SKILL.md')

    # Sandbox configuration (LangBot-local security policy)
    sandbox_timeout_sec = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=120)
    sandbox_network = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    # Governance status
    is_enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    is_builtin = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

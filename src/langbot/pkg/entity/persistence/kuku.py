from __future__ import annotations

import sqlalchemy

from .base import Base


class KukuGroupSetting(Base):
    __tablename__ = 'kuku_group_settings'
    __table_args__ = (
        sqlalchemy.UniqueConstraint('bot_uuid', 'platform', 'group_id', name='uq_kuku_group_settings_scope'),
    )

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    platform = sqlalchemy.Column(sqlalchemy.String(32), nullable=False)
    group_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    persona_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    silence_seconds = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=1800)
    quiet_hours = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    cooldown_minutes = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=10)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

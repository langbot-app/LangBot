import sqlalchemy

from .base import Base


class WecomCSCursorCheckpoint(Base):
    """Persistent cursor checkpoint for WeCom customer service sync."""

    __tablename__ = 'wecomcs_cursor_checkpoints'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    open_kfid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    cursor = sqlalchemy.Column(sqlalchemy.Text, nullable=False, default='')
    bootstrapped = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
    __table_args__ = (
        sqlalchemy.UniqueConstraint('bot_uuid', 'open_kfid', name='uq_wecomcs_cursor_bot_openkfid'),
    )

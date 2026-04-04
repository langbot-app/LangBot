import sqlalchemy

from .base import Base


class HumanTakeoverSession(Base):
    """Human takeover session records.

    Tracks which conversation sessions are currently under human operator control,
    bypassing the normal AI pipeline processing.
    """

    __tablename__ = 'human_takeover_sessions'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    """Corresponds to monitoring_sessions.session_id, format: 'person_{id}' or 'group_{id}'"""

    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """UUID of the bot whose session is being taken over"""

    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='active', index=True)
    """Takeover status: 'active' or 'released'"""

    taken_by = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Email/username of the admin who took over the session"""

    taken_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    """Timestamp when the takeover started"""

    released_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """Timestamp when the takeover was released (null if still active)"""

    platform = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    user_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)

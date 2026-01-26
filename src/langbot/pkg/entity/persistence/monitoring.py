import sqlalchemy

from .base import Base


class MonitoringMessage(Base):
    """Monitoring message records"""

    __tablename__ = 'monitoring_messages'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    timestamp = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    bot_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    pipeline_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    message_content = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)  # success, error, pending
    level = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)  # info, warning, error, debug
    platform = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    runner_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)  # Runner name for this query
    variables = sqlalchemy.Column(sqlalchemy.Text, nullable=True)  # Query variables as JSON string


class MonitoringLLMCall(Base):
    """LLM call records"""

    __tablename__ = 'monitoring_llm_calls'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    timestamp = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    model_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    input_tokens = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    output_tokens = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    total_tokens = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    duration = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)  # milliseconds
    cost = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)  # success, error
    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    bot_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    pipeline_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    error_message = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    message_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)  # Associated message ID


class MonitoringSession(Base):
    """Session tracking records"""

    __tablename__ = 'monitoring_sessions'

    session_id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    bot_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    pipeline_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    message_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    start_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    last_activity = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    is_active = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, index=True)
    platform = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)


class MonitoringError(Base):
    """Error log records"""

    __tablename__ = 'monitoring_errors'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    timestamp = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    error_type = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    error_message = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    bot_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    pipeline_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    stack_trace = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    message_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)  # Associated message ID


class MonitoringEmbeddingCall(Base):
    """Embedding call records"""

    __tablename__ = 'monitoring_embedding_calls'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    timestamp = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, index=True)
    model_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    prompt_tokens = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    total_tokens = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    duration = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)  # milliseconds
    input_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)  # Number of input texts
    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)  # success, error
    error_message = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    # Optional context fields
    knowledge_base_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    query_text = sqlalchemy.Column(sqlalchemy.Text, nullable=True)  # For retrieval calls
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    message_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    call_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)  # embedding, retrieve

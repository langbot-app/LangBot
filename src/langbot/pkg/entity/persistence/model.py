import sqlalchemy

from .base import Base


class ModelProvider(Base):
    """Model provider"""

    __tablename__ = 'model_providers'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    requester = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    base_url = sqlalchemy.Column(sqlalchemy.String(512), nullable=False)
    api_keys = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class LLMModel(Base):
    """LLM model"""

    __tablename__ = 'llm_models'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    provider_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    abilities = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class EmbeddingModel(Base):
    """Embedding model"""

    __tablename__ = 'embedding_models'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    provider_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

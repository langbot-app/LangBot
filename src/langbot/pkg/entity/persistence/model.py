import sqlalchemy

from .base import Base


class ModelProvider(Base):
    """Model provider"""

    __tablename__ = 'model_providers'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
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

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'uuid', name='uq_model_providers_workspace_uuid'),
        sqlalchemy.Index('ix_model_providers_workspace_name', 'workspace_uuid', 'name'),
        sqlalchemy.Index('ix_model_providers_workspace_requester', 'workspace_uuid', 'requester'),
    )


class LLMModel(Base):
    """LLM model"""

    __tablename__ = 'llm_models'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    provider_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    abilities = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    context_length = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    prefered_ranking = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'provider_uuid'],
            ['model_providers.workspace_uuid', 'model_providers.uuid'],
            name='fk_llm_models_workspace_provider',
        ),
        sqlalchemy.Index('ix_llm_models_workspace_provider', 'workspace_uuid', 'provider_uuid'),
        sqlalchemy.Index('ix_llm_models_workspace_name', 'workspace_uuid', 'name'),
    )


class EmbeddingModel(Base):
    """Embedding model"""

    __tablename__ = 'embedding_models'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    provider_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    prefered_ranking = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'provider_uuid'],
            ['model_providers.workspace_uuid', 'model_providers.uuid'],
            name='fk_embedding_models_workspace_provider',
        ),
        sqlalchemy.Index('ix_embedding_models_workspace_provider', 'workspace_uuid', 'provider_uuid'),
        sqlalchemy.Index('ix_embedding_models_workspace_name', 'workspace_uuid', 'name'),
    )


class RerankModel(Base):
    """Rerank model"""

    __tablename__ = 'rerank_models'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    provider_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    prefered_ranking = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'provider_uuid'],
            ['model_providers.workspace_uuid', 'model_providers.uuid'],
            name='fk_rerank_models_workspace_provider',
        ),
        sqlalchemy.Index('ix_rerank_models_workspace_provider', 'workspace_uuid', 'provider_uuid'),
        sqlalchemy.Index('ix_rerank_models_workspace_name', 'workspace_uuid', 'name'),
    )

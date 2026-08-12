import sqlalchemy
from .base import Base


class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String, index=True)
    description = sqlalchemy.Column(sqlalchemy.Text)
    emoji = sqlalchemy.Column(sqlalchemy.String(10), nullable=True, default='📚')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now())
    # New fields for plugin-based RAG
    knowledge_engine_plugin_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    collection_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Server-managed compatibility marker.  Pre-tenancy installations stored
    # vectors directly under ``collection_id``; new knowledge bases use a
    # tenant-derived opaque physical collection instead.
    legacy_vector_collection = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=False,
        server_default=sqlalchemy.false(),
    )
    creation_settings = sqlalchemy.Column(sqlalchemy.JSON, nullable=True, default=None)
    retrieval_settings = sqlalchemy.Column(sqlalchemy.JSON, nullable=True, default=None)
    # Server-selected pgvector dimension. ``None`` means no embedding has been
    # written yet; the first pgvector upsert binds it atomically.
    embedding_dimension = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)

    # Field sets for different operations
    MUTABLE_FIELDS = {'name', 'description', 'retrieval_settings'}
    """Fields that can be updated after creation."""

    CREATE_FIELDS = MUTABLE_FIELDS | {'uuid', 'knowledge_engine_plugin_id', 'collection_id', 'creation_settings'}
    """Fields used when creating a new knowledge base."""

    ALL_DB_FIELDS = CREATE_FIELDS | {
        'workspace_uuid',
        'legacy_vector_collection',
        'embedding_dimension',
        'emoji',
        'created_at',
        'updated_at',
    }
    """All fields stored in database (for loading from DB row)."""

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'uuid', name='uq_knowledge_bases_workspace_uuid'),
        sqlalchemy.Index('ix_knowledge_bases_workspace_name', 'workspace_uuid', 'name'),
        sqlalchemy.Index(
            'uq_knowledge_bases_workspace_collection',
            'workspace_uuid',
            'collection_id',
            unique=True,
            sqlite_where=sqlalchemy.text('collection_id IS NOT NULL'),
            postgresql_where=sqlalchemy.text('collection_id IS NOT NULL'),
        ),
        sqlalchemy.CheckConstraint(
            'embedding_dimension IS NULL OR embedding_dimension > 0',
            name='ck_knowledge_bases_embedding_dimension_positive',
        ),
    )


class File(Base):
    __tablename__ = 'knowledge_base_files'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    kb_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    file_name = sqlalchemy.Column(sqlalchemy.String)
    extension = sqlalchemy.Column(sqlalchemy.String)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    status = sqlalchemy.Column(sqlalchemy.String, default='pending')  # pending, processing, completed, failed

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'uuid', name='uq_knowledge_base_files_workspace_uuid'),
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'kb_id'],
            ['knowledge_bases.workspace_uuid', 'knowledge_bases.uuid'],
            name='fk_knowledge_base_files_workspace_kb',
            ondelete='CASCADE',
        ),
        sqlalchemy.Index('ix_knowledge_base_files_workspace_kb', 'workspace_uuid', 'kb_id'),
    )


class Chunk(Base):
    __tablename__ = 'knowledge_base_chunks'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    file_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    text = sqlalchemy.Column(sqlalchemy.Text)

    __table_args__ = (
        sqlalchemy.ForeignKeyConstraint(
            ['workspace_uuid', 'file_id'],
            ['knowledge_base_files.workspace_uuid', 'knowledge_base_files.uuid'],
            name='fk_knowledge_base_chunks_workspace_file',
            ondelete='CASCADE',
        ),
        sqlalchemy.Index('ix_knowledge_base_chunks_workspace_file', 'workspace_uuid', 'file_id'),
    )

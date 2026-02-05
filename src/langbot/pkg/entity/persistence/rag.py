import sqlalchemy
from .base import Base


class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, index=True)
    description = sqlalchemy.Column(sqlalchemy.Text)
    emoji = sqlalchemy.Column(sqlalchemy.String(10), nullable=True, default='📚')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now())
    embedding_model_uuid = sqlalchemy.Column(sqlalchemy.String, default='')
    top_k = sqlalchemy.Column(sqlalchemy.Integer, default=5)

    # New fields for plugin-based RAG
    rag_engine_plugin_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    collection_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    creation_settings = sqlalchemy.Column(sqlalchemy.JSON, nullable=True, default={})

    # Field sets for different operations
    MUTABLE_FIELDS = {'name', 'description', 'top_k', 'rag_engine_plugin_id', 'creation_settings', 'embedding_model_uuid'}
    """Fields that can be updated after creation."""

    CREATE_FIELDS = MUTABLE_FIELDS | {'uuid'}
    """Fields used when creating a new knowledge base."""

    ALL_DB_FIELDS = CREATE_FIELDS | {'created_at', 'updated_at'}
    """All fields stored in database (for loading from DB row)."""


class File(Base):
    __tablename__ = 'knowledge_base_files'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    kb_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    file_name = sqlalchemy.Column(sqlalchemy.String)
    extension = sqlalchemy.Column(sqlalchemy.String)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    status = sqlalchemy.Column(sqlalchemy.String, default='pending')  # pending, processing, completed, failed


class Chunk(Base):
    __tablename__ = 'knowledge_base_chunks'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    file_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    text = sqlalchemy.Column(sqlalchemy.Text)

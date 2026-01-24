import sqlalchemy
from .base import Base


class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, index=True)
    description = sqlalchemy.Column(sqlalchemy.Text)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now(), onupdate=sqlalchemy.func.now())
    embedding_model_uuid = sqlalchemy.Column(sqlalchemy.String, default='')
    top_k = sqlalchemy.Column(sqlalchemy.Integer, default=5)
    
    # New fields for plugin-based RAG
    rag_engine_plugin_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    collection_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    creation_settings = sqlalchemy.Column(sqlalchemy.JSON, nullable=True, default={})


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


class ExternalKnowledgeBase(Base):
    __tablename__ = 'external_knowledge_bases'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, index=True)
    description = sqlalchemy.Column(sqlalchemy.Text)
    plugin_author = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    plugin_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    retriever_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    retriever_config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())

import sqlalchemy

from .base import Base


class LLMModel(Base):
    """LLM 模型"""
    __tablename__ = 'llm_models'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    requester = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    requester_config = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    api_keys = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    abilities = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=[])
    extra_args = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
from __future__ import annotations

from ..core import app
from .vdb import VectorDatabase
from .vdbs.chroma import ChromaVectorDatabase


class VectorDBManager:
    ap: app.Application
    vector_db: VectorDatabase = None

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        # 初始化 Chroma 向量数据库（可扩展为多种实现）
        if self.vector_db is None:
            self.vector_db = ChromaVectorDatabase(self.ap)

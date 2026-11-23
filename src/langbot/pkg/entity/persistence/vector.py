from sqlalchemy import Column, Integer, ForeignKey, LargeBinary
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Vector(Base):
    __tablename__ = 'vectors'
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey('chunks.id'), unique=True)
    embedding = Column(LargeBinary)  # Store embeddings as binary

    chunk = relationship('Chunk', back_populates='vector')

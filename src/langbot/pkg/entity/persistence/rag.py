import sqlalchemy
from .base import Base

# Base = declarative_base()
# DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./rag_knowledge.db')
# print("Using database URL:", DATABASE_URL)


# engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# def create_db_and_tables():
#     """Creates all database tables defined in the Base."""
#     Base.metadata.create_all(bind=engine)
#     print('Database tables created or already exist.')


class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, index=True)
    description = sqlalchemy.Column(sqlalchemy.Text)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())
    embedding_model_uuid = sqlalchemy.Column(sqlalchemy.String, default='')
    top_k = sqlalchemy.Column(sqlalchemy.Integer, default=5)


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


# class Vector(Base):
#     __tablename__ = 'knowledge_base_vectors'
#     uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
#     chunk_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
#     embedding = sqlalchemy.Column(sqlalchemy.LargeBinary)

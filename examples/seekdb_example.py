"""
Example demonstrating how to use SeekDB as the vector database backend in LangBot.

This example shows:
1. Configuration setup for embedded mode
2. Configuration setup for server mode
3. How SeekDB integrates seamlessly with LangBot's knowledge base system

Prerequisites:
- Install pyseekdb: pip install pyseekdb
- Configure config.yaml to use SeekDB
"""

# Example 1: Embedded Mode Configuration
# ======================================
#
# Add this to your config.yaml:
#
# vdb:
#   use: seekdb
#   seekdb:
#     mode: embedded
#     path: './data/seekdb'
#     database: 'langbot'
#
# Benefits:
# - No external server required
# - Perfect for development and testing
# - Lightweight and fast startup
# - Data stored locally

# Example 2: Server Mode Configuration
# =====================================
#
# For production deployments with SeekDB server:
#
# vdb:
#   use: seekdb
#   seekdb:
#     mode: server
#     host: 'localhost'
#     port: 2881
#     database: 'langbot'
#     user: 'root'
#     password: ''
#
# Benefits:
# - Scalable for production
# - Centralized data management
# - Better performance for large datasets
# - Can use remote OceanBase server

# Example 3: OceanBase Server Configuration
# ==========================================
#
# For using with OceanBase distributed database:
#
# vdb:
#   use: seekdb
#   seekdb:
#     mode: server
#     host: 'oceanbase.example.com'
#     port: 2881
#     tenant: 'sys'
#     database: 'langbot'
#     user: 'root'
#     password: 'your_password'
#
# Benefits:
# - Distributed architecture for high availability
# - Full MySQL compatibility
# - Enterprise-grade features
# - Hybrid search capabilities (vector + full-text + SQL)

# Example 4: Using in Python Code
# ================================
#
# Once configured, SeekDB works transparently with LangBot's knowledge base:


async def example_usage():
    """
    Example of how SeekDB is used automatically by LangBot's knowledge base system.
    No code changes required - just configure and use!
    """
    from langbot.pkg.core import app
    from langbot.pkg.rag.knowledge.kbmgr import KnowledgeBaseManager

    # Initialize application (reads config.yaml)
    application = app.Application()
    await application.initialize()

    # The vector database manager will automatically use SeekDB based on config
    vector_db = application.vector_db_mgr.vector_db
    print(f'Using vector database: {type(vector_db).__name__}')
    # Output: "Using vector database: SeekDBVectorDatabase"

    # Create a knowledge base - vectors will be stored in SeekDB
    kb_mgr = KnowledgeBaseManager(application)
    kb = await kb_mgr.create_knowledge_base(
        name='My Knowledge Base', description='Example KB using SeekDB', embedding_model_id='text-embedding-3-small'
    )

    # Add documents - embeddings will be stored in SeekDB
    await kb_mgr.add_document(kb_id=kb.id, file_path='example.pdf', chunk_size=500)

    # Search - uses SeekDB's efficient vector search
    results = await kb_mgr.search(kb_id=kb.id, query='What is AI?', top_k=5)

    print(f'Found {len(results)} results using SeekDB')


# Example 5: Direct Vector Database Operations
# =============================================
#
# For advanced use cases, you can access the vector database directly:


async def advanced_usage():
    """Direct vector database operations (advanced)."""
    from langbot.pkg.core import app

    application = app.Application()
    await application.initialize()

    vdb = application.vector_db_mgr.vector_db

    # Create a collection
    await vdb.get_or_create_collection('test_collection')

    # Add embeddings
    await vdb.add_embeddings(
        collection='test_collection',
        ids=['doc1', 'doc2', 'doc3'],
        embeddings_list=[
            [0.1, 0.2, 0.3] * 128,  # 384-dim vector
            [0.4, 0.5, 0.6] * 128,
            [0.7, 0.8, 0.9] * 128,
        ],
        metadatas=[
            {'file_id': 'file1', 'text': 'Document 1'},
            {'file_id': 'file1', 'text': 'Document 2'},
            {'file_id': 'file2', 'text': 'Document 3'},
        ],
    )

    # Search
    query_vector = [0.15, 0.25, 0.35] * 128
    results = await vdb.search(collection='test_collection', query_embedding=query_vector, k=2)

    print('Search results:', results)

    # Delete by file_id
    await vdb.delete_by_file_id(collection='test_collection', file_id='file1')

    # Delete collection
    await vdb.delete_collection('test_collection')


# Comparison with Other Vector Databases
# =======================================
#
# SeekDB vs ChromaDB:
# - ✅ Better MySQL compatibility
# - ✅ Hybrid search (vector + full-text + SQL)
# - ✅ Production-grade distributed mode
# - ✅ Same embedded mode convenience
#
# SeekDB vs Qdrant:
# - ✅ SQL query support
# - ✅ MySQL ecosystem integration
# - ✅ Simpler deployment (no Docker required)
# - ✅ Multi-model data support
#
# When to use SeekDB:
# - Need MySQL compatibility
# - Want hybrid search capabilities
# - Require SQL querying on vector data
# - Building enterprise applications
# - Need lightweight embedded mode for dev/testing

if __name__ == '__main__':
    print('SeekDB Integration Example')
    print('=' * 50)
    print()
    print('To use SeekDB with LangBot:')
    print('1. Install: pip install pyseekdb')
    print('2. Configure config.yaml (see examples above)')
    print('3. Run LangBot - SeekDB will be used automatically!')
    print()
    print('For detailed documentation, see:')
    print('docs/SEEKDB_INTEGRATION.md')

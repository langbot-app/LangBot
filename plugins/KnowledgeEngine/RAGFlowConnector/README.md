# RAGFlowConnector

Retrieve knowledge from or store files into RAGFlow knowledge bases using the RAGFlow API.

## About RAGFlow

RAGFlow is an open-source RAG (Retrieval-Augmented Generation) engine based on deep document understanding. It provides truthful question-answering capabilities with well-founded citations from various complex formatted data.

## Features

- Retrieve knowledge chunks from RAGFlow datasets/knowledge bases
- Upload and ingest files into RAGFlow datasets with automatic parsing
- Support for multiple datasets in a single query
- Configurable similarity thresholds and vector weights
- Hybrid search combining keyword and vector similarity
- Auto-trigger GraphRAG knowledge graph construction after ingestion
- Auto-trigger RAPTOR hierarchical summarization after ingestion
- Dataset ID validation on knowledge base creation
- Returns results with rich metadata including term and vector similarity scores

## Configuration

This plugin requires the following configuration parameters:

### Required Parameters (Creation Settings)

- **api_base_url**: Base URL for RAGFlow API
  - For local deployment: `http://localhost:9380` (default)
  - For remote server: Your server URL (e.g., `http://your-domain.com:9380`)
- **api_key**: Your RAGFlow API key from your RAGFlow instance
- **dataset_ids**: Comma-separated dataset IDs to search
  - Format: `"dataset_id1,dataset_id2,dataset_id3"`
  - Example: `"b2a62730759d11ef987d0242ac120004,a3b52830859d11ef887d0242ac120005"`

### Optional Parameters (Creation Settings)

- **auto_graphrag** (default: false): Automatically trigger GraphRAG knowledge graph construction after file ingestion
- **auto_raptor** (default: false): Automatically trigger RAPTOR hierarchical summarization after file ingestion

### Optional Parameters (Retrieval Settings)

- **top_k** (default: 1024): Maximum number of retrieved results
- **similarity_threshold** (default: 0.2): Minimum similarity score (0-1)
- **vector_similarity_weight** (default: 0.3): Weight for vector similarity in hybrid search (0-1)
- **page_size** (default: 30): Number of results per page
- **keyword** (default: false): Use LLM to extract keywords from query to enhance retrieval
- **rerank_id**: Rerank model ID configured in RAGFlow (e.g., `BAAI/bge-reranker-v2-m3`)
- **use_kg** (default: false): Enable knowledge graph retrieval

## How to Get Configuration Values

### Getting your RAGFlow API Key

1. Access your RAGFlow instance (e.g., `http://localhost:9380`)
2. Navigate to **User Settings** > **API** section
3. Generate or copy your API key (format: `ragflow-xxxxx`)

### Getting your Dataset IDs

1. In RAGFlow, go to your knowledge base/dataset list
2. Click on a dataset to view its details
3. The dataset ID is typically shown in the URL or dataset details
4. For multiple datasets, collect all IDs and join them with commas

## API Reference

This plugin uses the following RAGFlow APIs:
- Retrieval: `POST /api/v1/retrieval`
- Upload documents: `POST /api/v1/datasets/{dataset_id}/documents`
- Parse documents: `POST /api/v1/datasets/{dataset_id}/chunks`
- Delete documents: `DELETE /api/v1/datasets/{dataset_id}/documents`
- GraphRAG construction: `POST /api/v1/datasets/{dataset_id}/run_graphrag`
- RAPTOR construction: `POST /api/v1/datasets/{dataset_id}/run_raptor`
- List datasets (validation): `GET /api/v1/datasets`
- Documentation: https://ragflow.io/docs/dev/http_api_reference

## Retrieval Method

RAGFlow employs a hybrid retrieval approach:
- **Keyword Similarity**: Traditional keyword-based matching
- **Vector Similarity**: Semantic similarity using embeddings
- **Weighted Combination**: Combines both methods with configurable weights
- **Knowledge Graph**: Optional graph-based retrieval for relationship-aware answers
- **Reranking**: Optional reranking model for improved result quality

The `vector_similarity_weight` parameter controls the balance between keyword and vector methods.

## Runtime placement

This version remains dedicated. SDK 0.7.4 shared singleton placement requires a
signed `stateless-v1` component model, not just `shared-runtime-v1`.
The existing per-installation mutation state and cancellation model have
not passed that contract. See [the audit](../SHARED_RUNTIME.md).

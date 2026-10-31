# DifyDatasetsConnector

Retrieve knowledge from or store files into Dify knowledge bases using the Dify API.

## Configuration

Please add an external knowledge base in LangBot and select "DifyDatasetsConnector" as the knowledge retriever type.

### Creation Settings (set when creating a knowledge base)

- **api_base_url**: Base URL for Dify API
  - For Dify Cloud: `https://api.dify.ai/v1` (default)
  - For self-hosted instances: Your server URL (e.g., `http://localhost/api` or `https://your-domain.com/api`)
- **dify_apikey**: Your Dify API key from your Dify instance
- **dataset_id**: The ID of your Dify knowledge base/dataset

### Retrieval Settings (adjustable per query)

- **search_method** (default: semantic_search): The search method to use
  - `keyword_search`: Keyword-based search
  - `semantic_search`: Semantic similarity search (default)
  - `full_text_search`: Full-text search
  - `hybrid_search`: Hybrid search combining semantic and full-text
- **top_k** (default: 5): Maximum number of retrieved results
- **score_threshold_enabled** (default: false): Whether to enable score threshold filtering
- **score_threshold** (default: 0.5): Minimum relevance score (0-1), only shown when score threshold is enabled
- **reranking_enable** (default: false): Enable reranking to improve result quality. The reranking model is automatically fetched from your Dify dataset settings — please configure the reranking model in the Dify console first

## How to Get Configuration Values

### Getting your Dify API Key

1. Go to https://cloud.dify.ai/
2. Navigate to your knowledge base page
3. Click on "API ACCESS" in the left sidebar
4. Create or copy your API key from the "API Keys" section

### Getting your Dataset ID

1. In the Dify knowledge base list, click on your knowledge base
2. The dataset ID is in the URL: `https://cloud.dify.ai/datasets/{dataset_id}`
3. Or you can find it in the API documentation page of your knowledge base

### Configuring Reranking

1. In the Dify console, go to your dataset settings
2. Enable reranking and select a reranking model (e.g., `cohere/rerank-v3.5`)
3. Save the settings
4. In LangBot, enable the "Enable Reranking" toggle — the plugin will automatically use the model configured in Dify

## API Reference

This plugin uses the Dify Dataset API:
- Retrieval: `POST /v1/datasets/{dataset_id}/retrieve`
- Dataset info: `GET /v1/datasets/{dataset_id}`
- Document upload: `POST /v1/datasets/{dataset_id}/document/create-by-file`
- Document delete: `DELETE /v1/datasets/{dataset_id}/documents/{document_id}`
- Documentation: https://docs.dify.ai/

## Runtime placement

This version remains dedicated. SDK 0.7.4 shared singleton placement requires a
signed `stateless-v1` component model, not just `shared-runtime-v1`.
The existing per-installation mutation state and cancellation model have
not passed that contract. See [the audit](../SHARED_RUNTIME.md).

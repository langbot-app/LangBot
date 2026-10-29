# FastGPTConnector

Retrieve knowledge from FastGPT knowledge bases using the FastGPT API.

## About FastGPT

FastGPT is an open-source knowledge base question-answering system built on LLM models. It provides an out-of-the-box data processing and model invocation capabilities for complex question-answering scenarios.

## Features

- Search and retrieve knowledge from FastGPT datasets/knowledge bases
- Support multiple search modes (embedding, full-text recall, mixed recall)
- Configurable similarity thresholds and token limits
- Optional re-ranking for better results
- Query optimization with extension models

## Configuration

This plugin requires the following configuration parameters:

### Required Parameters

- **api_base_url**: Base URL for FastGPT API
  - For local deployment: `http://localhost:3000` (default)
  - For remote server: Your server URL (e.g., `https://your-domain.com`)
- **api_key**: Your FastGPT API key
  - Format: `fastgpt-xxxxx`
- **dataset_id**: The ID of your FastGPT knowledge base/dataset

### Optional Parameters

- **limit** (default: 5000): Maximum number of tokens to retrieve
- **similarity** (default: 0.0): Minimum similarity score (0-1)
- **search_mode** (default: embedding): The search method to use
  - `embedding`: Semantic embedding search
  - `fullTextRecall`: Full-text keyword search
  - `mixedRecall`: Mixed search combining both methods
- **using_rerank** (default: false): Whether to use re-ranking
- **dataset_search_using_extension_query** (default: false): Whether to use query optimization
- **dataset_search_extension_model** (optional): Model for query optimization
- **dataset_search_extension_bg** (optional): Background description for query optimization

## How to Get Configuration Values

### Getting your FastGPT API Key

1. Access your FastGPT instance (e.g., `http://localhost:3000`)
2. Navigate to the API management or settings section
3. Create or copy your API key (format: `fastgpt-xxxxx`)

### Getting your Dataset ID

1. In FastGPT, go to your knowledge base list
2. Click on a knowledge base to view its details
3. The dataset ID can be found in the URL or dataset details page

## API Reference

This plugin uses the FastGPT Dataset Search Test API:
- Endpoint: `POST /api/core/dataset/searchTest`
- Documentation: https://doc.fastgpt.io/docs/introduction/development/openapi/dataset

## Search Methods

### Embedding Search
Uses semantic similarity based on vector embeddings. Best for understanding query intent and finding semantically related content.

### Full-Text Recall
Traditional keyword-based full-text search. Best for finding exact matches and specific terms.

### Mixed Recall
Combines both embedding and full-text search methods. Provides balanced results with both semantic understanding and keyword matching.

## Runtime placement

This version remains dedicated. SDK 0.7.4 shared singleton placement requires a
signed `stateless-v1` component model, not just `shared-runtime-v1`.
The existing per-installation mutation state and cancellation model have
not passed that contract. See [the audit](../SHARED_RUNTIME.md).

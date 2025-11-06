# API Key Authentication

LangBot now supports API key authentication for external systems to access its HTTP service API.

## Managing API Keys

API keys can be managed through the web interface:

1. Log in to the LangBot web interface
2. Click the "API Keys" button at the bottom of the sidebar
3. Create, view, copy, or delete API keys as needed

## Using API Keys

### Authentication Headers

Include your API key in the request header using one of these methods:

**Method 1: X-API-Key header**
```
X-API-Key: lbk_your_api_key_here
```

**Method 2: Authorization Bearer token**
```
Authorization: Bearer lbk_your_api_key_here
```

## Available Service APIs

### LLM Model Management

All LLM model management endpoints require API key authentication.

#### List All LLM Models

```http
GET /api/service/v1/models/llm
X-API-Key: lbk_your_api_key_here
```

Response:
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "models": [
      {
        "uuid": "model-uuid",
        "name": "GPT-4",
        "description": "OpenAI GPT-4 model",
        "requester": "openai-chat-completions",
        "requester_config": {...},
        "abilities": ["chat", "vision"],
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
      }
    ]
  }
}
```

#### Get a Specific LLM Model

```http
GET /api/service/v1/models/llm/{model_uuid}
X-API-Key: lbk_your_api_key_here
```

#### Create a New LLM Model

```http
POST /api/service/v1/models/llm
X-API-Key: lbk_your_api_key_here
Content-Type: application/json

{
  "name": "My Custom Model",
  "description": "Description of the model",
  "requester": "openai-chat-completions",
  "requester_config": {
    "model": "gpt-4",
    "args": {}
  },
  "api_keys": [
    {
      "name": "default",
      "keys": ["sk-..."]
    }
  ],
  "abilities": ["chat"],
  "extra_args": {}
}
```

Response:
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "uuid": "newly-created-model-uuid"
  }
}
```

#### Update an LLM Model

```http
PUT /api/service/v1/models/llm/{model_uuid}
X-API-Key: lbk_your_api_key_here
Content-Type: application/json

{
  "name": "Updated Model Name",
  "description": "Updated description",
  ...
}
```

#### Delete an LLM Model

```http
DELETE /api/service/v1/models/llm/{model_uuid}
X-API-Key: lbk_your_api_key_here
```

#### Test an LLM Model

```http
POST /api/service/v1/models/llm/{model_uuid}/test
X-API-Key: lbk_your_api_key_here
Content-Type: application/json

{
  // Model configuration to test
}
```

## Error Responses

### 401 Unauthorized

```json
{
  "code": -1,
  "msg": "No valid API key provided"
}
```

or

```json
{
  "code": -1,
  "msg": "Invalid API key"
}
```

### 404 Not Found

```json
{
  "code": -1,
  "msg": "Model not found"
}
```

### 500 Internal Server Error

```json
{
  "code": -2,
  "msg": "Error message details"
}
```

## Security Best Practices

1. **Keep API keys secure**: Store them securely and never commit them to version control
2. **Use HTTPS**: Always use HTTPS in production to encrypt API key transmission
3. **Rotate keys regularly**: Create new API keys periodically and delete old ones
4. **Use descriptive names**: Give your API keys meaningful names to track their usage
5. **Delete unused keys**: Remove API keys that are no longer needed

## Example: Python Client

```python
import requests

API_KEY = "lbk_your_api_key_here"
BASE_URL = "http://your-langbot-server:5300"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# List all models
response = requests.get(f"{BASE_URL}/api/service/v1/models/llm", headers=headers)
models = response.json()["data"]["models"]

print(f"Found {len(models)} models")
for model in models:
    print(f"- {model['name']}: {model['description']}")
```

## Example: cURL

```bash
# List all models
curl -X GET \
  -H "X-API-Key: lbk_your_api_key_here" \
  http://your-langbot-server:5300/api/service/v1/models/llm

# Create a new model
curl -X POST \
  -H "X-API-Key: lbk_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Model",
    "description": "Test model",
    "requester": "openai-chat-completions",
    "requester_config": {"model": "gpt-4", "args": {}},
    "api_keys": [{"name": "default", "keys": ["sk-..."]}],
    "abilities": ["chat"]
  }' \
  http://your-langbot-server:5300/api/service/v1/models/llm
```

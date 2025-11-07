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

**Method 1: X-API-Key header (Recommended)**
```
X-API-Key: lbk_your_api_key_here
```

**Method 2: Authorization Bearer token**
```
Authorization: Bearer lbk_your_api_key_here
```

## Available APIs

All existing LangBot APIs now support **both user token and API key authentication**. This means you can use API keys to access:

- **Model Management** - `/api/v1/provider/models/llm` and `/api/v1/provider/models/embedding`
- **Bot Management** - `/api/v1/platform/bots`
- **Pipeline Management** - `/api/v1/pipelines`
- **Knowledge Base** - `/api/v1/knowledge/*`
- **MCP Servers** - `/api/v1/mcp/servers`
- And more...

### Authentication Methods

Each endpoint accepts **either**:
1. **User Token** (via `Authorization: Bearer <user_jwt_token>`) - for web UI and authenticated users
2. **API Key** (via `X-API-Key` or `Authorization: Bearer <api_key>`) - for external services

## Example: Model Management

### List All LLM Models

```http
GET /api/v1/provider/models/llm
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

### Create a New LLM Model

```http
POST /api/v1/provider/models/llm
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

### Update an LLM Model

```http
PUT /api/v1/provider/models/llm/{model_uuid}
X-API-Key: lbk_your_api_key_here
Content-Type: application/json

{
  "name": "Updated Model Name",
  "description": "Updated description",
  ...
}
```

### Delete an LLM Model

```http
DELETE /api/v1/provider/models/llm/{model_uuid}
X-API-Key: lbk_your_api_key_here
```

## Example: Bot Management

### List All Bots

```http
GET /api/v1/platform/bots
X-API-Key: lbk_your_api_key_here
```

### Create a New Bot

```http
POST /api/v1/platform/bots
X-API-Key: lbk_your_api_key_here
Content-Type: application/json

{
  "name": "My Bot",
  "adapter": "telegram",
  "config": {...}
}
```

## Example: Pipeline Management

### List All Pipelines

```http
GET /api/v1/pipelines
X-API-Key: lbk_your_api_key_here
```

### Create a New Pipeline

```http
POST /api/v1/pipelines
X-API-Key: lbk_your_api_key_here
Content-Type: application/json

{
  "name": "My Pipeline",
  "config": {...}
}
```

## Error Responses

### 401 Unauthorized

```json
{
  "code": -1,
  "msg": "No valid authentication provided (user token or API key required)"
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
  "msg": "Resource not found"
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
6. **Use X-API-Key header**: Prefer using the `X-API-Key` header for clarity

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
response = requests.get(f"{BASE_URL}/api/v1/provider/models/llm", headers=headers)
models = response.json()["data"]["models"]

print(f"Found {len(models)} models")
for model in models:
    print(f"- {model['name']}: {model['description']}")

# Create a new bot
bot_data = {
    "name": "My Telegram Bot",
    "adapter": "telegram",
    "config": {
        "token": "your-telegram-token"
    }
}

response = requests.post(
    f"{BASE_URL}/api/v1/platform/bots",
    headers=headers,
    json=bot_data
)

if response.status_code == 200:
    bot_uuid = response.json()["data"]["uuid"]
    print(f"Bot created with UUID: {bot_uuid}")
```

## Example: cURL

```bash
# List all models
curl -X GET \
  -H "X-API-Key: lbk_your_api_key_here" \
  http://your-langbot-server:5300/api/v1/provider/models/llm

# Create a new pipeline
curl -X POST \
  -H "X-API-Key: lbk_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Pipeline",
    "config": {...}
  }' \
  http://your-langbot-server:5300/api/v1/pipelines

# Get bot logs
curl -X POST \
  -H "X-API-Key: lbk_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "from_index": -1,
    "max_count": 10
  }' \
  http://your-langbot-server:5300/api/v1/platform/bots/{bot_uuid}/logs
```

## Notes

- The same endpoints work for both the web UI (with user tokens) and external services (with API keys)
- No need to learn different API paths - use the existing API documentation with API key authentication
- All endpoints that previously required user authentication now also accept API keys


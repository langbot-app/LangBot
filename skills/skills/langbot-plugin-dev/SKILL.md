---
name: langbot-plugin-dev
description: Develop, debug, and test LangBot plugins. Use when creating new LangBot plugins, fixing plugin bugs, setting up a LangBot test environment, or testing plugins via WebSocket. Covers plugin component architecture (EventListener, Command, Tool), the plugin SDK API (invoke_llm, get_llm_models, send_message, plugin storage), common pitfalls, and automated WebSocket-based testing. Triggers on "langbot plugin", "lbp", "GroupChatSummary", "plugin debug", "langbot test".
---

# LangBot Plugin Development & Debugging

## Controlling a running instance via MCP

Beyond writing code, you can **drive a live LangBot instance over MCP** — no raw
HTTP needed. Two MCP servers exist (both reuse existing API keys; see `AGENTS.md`):

- **LangBot instance** — `http://<host>:5300/mcp` (auth: web-UI `lbk_` key or the
  `api.global_api_key` from `config.yaml`). Manage bots, pipelines, models,
  knowledge bases, and skills. See the **`langbot-mcp-ops`** skill.
- **LangBot Space marketplace** — `https://space.langbot.app/mcp` (auth: Personal
  Access Token). Search plugins / MCP servers / skills. See the
  **`langbot-space-ops`** skill.

> Any change to an agent-accessible HTTP API endpoint must keep the matching MCP
> tool and these skills in sync.

## Plugin Architecture

A LangBot plugin consists of:

```
MyPlugin/
├── manifest.yaml          # Plugin metadata, config schema
├── main.py                # BasePlugin subclass (entry point, shared state)
├── components/
│   ├── event_listener/    # Hook pipeline events
│   │   ├── collector.yaml
│   │   └── collector.py
│   ├── commands/          # !command handlers
│   │   ├── mycommand.yaml
│   │   └── mycommand.py
│   └── tools/             # LLM function-call tools
│       ├── mytool.yaml
│       └── mytool.py
```

Each component has a `.yaml` (metadata) and `.py` (implementation).

## README & i18n convention (enforced on the marketplace)

A plugin published to LangBot Space serves a localized README on its detail page.
The resolver (`langbot-space` `PluginService.GetPluginREADME`) works like this:

- **Root `README.md` MUST be in English.** It is the default and the fallback —
  when no per-language README matches the viewer's locale, the page serves the
  root `README.md`. A non-English root README makes the English/default view show
  the wrong language.
- **All other languages live under `readme/README_{lang}.md`** — e.g.
  `readme/README_zh_Hans.md`, `readme/README_ja_JP.md`. The 8 supported locales:
  `en_US, zh_Hans, zh_Hant, ja_JP, th_TH, vi_VN, es_ES, ru_RU`.
- `manifest.yaml` `metadata.label` / `metadata.description` should carry the same
  8-locale i18n set (`repository` must be a real, alive URL).

```
MyPlugin/
├── manifest.yaml
├── README.md                   # English (default + fallback) — REQUIRED, must be English
└── readme/
    ├── README_zh_Hans.md
    ├── README_zh_Hant.md
    ├── README_ja_JP.md
    ├── README_th_TH.md
    ├── README_vi_VN.md
    ├── README_es_ES.md
    └── README_ru_RU.md
```

`manifest.yaml` (incl. `repository`) is the source of truth — the marketplace
syncs from it, so edit the package and re-publish rather than patching live data.

## Critical SDK Pitfalls

### 1. MessageChain is a RootModel — iterate directly

```python
# ❌ WRONG — MessageChain has no .components attribute
for component in event.message_chain.components:

# ✅ CORRECT — MessageChain is a Pydantic RootModel, iterate directly
for component in event.message_chain:
```

### 2. Message.content must be `list[ContentElement]` or `str`, not a single ContentElement

```python
from langbot_plugin.api.entities.builtin.provider import message as provider_message

# ❌ WRONG — single ContentElement
Message(role="user", content=ContentElement.from_text("hello"))

# ✅ CORRECT — list of ContentElement
Message(role="user", content=[ContentElement.from_text("hello")])

# ✅ ALSO CORRECT — plain string
Message(role="user", content="hello")
```

### 3. invoke_llm does NOT accept timeout

```python
# ❌ WRONG
await self.invoke_llm(llm_model_uuid=uuid, messages=msgs, timeout=60)

# ✅ CORRECT
await self.invoke_llm(llm_model_uuid=uuid, messages=msgs)
```

### 4. invoke_llm response.content can be str OR list

```python
response = await self.invoke_llm(...)
if response.content:
    if isinstance(response.content, str):
        return response.content
    elif isinstance(response.content, list):
        parts = [e.text for e in response.content if hasattr(e, "text") and e.text]
        return "\n".join(parts)
```

### 5. get_llm_models() returns UUIDs

```python
# Returns list[str] of model UUIDs
models = await self.get_llm_models()
model_uuid = models[0]  # First available model UUID
```

**Known bug (v4.9.3):** The host handler may return `list[dict]` instead of `list[str]`. If you hit `TypeError: unhashable type: 'dict'` in `invoke_llm`, the fix is in `LangBot/src/langbot/pkg/plugin/handler.py` — change `'llm_models': llm_models` to `'llm_models': [m['uuid'] for m in llm_models]`.

### 6. invoke_llm parameter is `llm_model_uuid`, NOT `model_uuid`

```python
# ❌ WRONG — will throw "got an unexpected keyword argument"
await self.invoke_llm(messages=msgs, model_uuid=uuid)

# ✅ CORRECT
await self.invoke_llm(messages=msgs, llm_model_uuid=uuid)
```

### 7. prevent_default() alone does NOT block LLM response

To fully prevent the default LLM pipeline from responding when your EventListener handles the message, you must call **both**:

```python
event_context.prevent_default()    # Block default behavior
event_context.prevent_postorder()  # Block subsequent plugins/pipeline
```

Using only `prevent_default()` still allows the LLM to generate a response.

### 8. get_plugin_storage / set_plugin_storage may throw KeyError: 'owner'

This is a version mismatch between the SDK and host. Wrap storage calls in try/except:

```python
try:
    data = await self.get_plugin_storage("my_key")
except Exception:
    data = None  # Fallback gracefully
```

### 9. Component YAML must have full structure, not just name/description

```yaml
# ❌ WRONG — will silently fail to register the component
name: translator
description:
  en_US: 'Does stuff'

# ✅ CORRECT — full component YAML
apiVersion: v1
kind: EventListener
metadata:
  name: translator
  label:
    en_US: Translator
spec:
execution:
  python:
    path: translator.py
    attr: Translator
```

### 10. BasePlugin import path

```python
# ❌ WRONG
from langbot_plugin.api.definition.base_plugin import BasePlugin

# ✅ CORRECT
from langbot_plugin.api.definition.plugin import BasePlugin
```

## Pipeline Events

Events the EventListener can hook (from most general to most specific):

| Event | When |
|---|---|
| `GroupMessageReceived` | **Any** group message arrives (before trigger rules) |
| `PersonMessageReceived` | **Any** private message arrives |
| `GroupNormalMessageReceived` | Group message passes trigger rules, going to LLM |
| `PersonNormalMessageReceived` | Private message going to LLM |
| `GroupCommandSent` | Group message matched as command |
| `PersonCommandSent` | Private message matched as command |
| `NormalMessageResponded` | LLM generated a response |
| `PromptPreProcessing` | About to build LLM context |

**Key insight:** `*MessageReceived` fires for ALL messages regardless of trigger rules. `*NormalMessageReceived` only fires for messages that match the pipeline's trigger rules (e.g., @bot, prefix, random%). Use `*MessageReceived` for message collection/logging.

## EventContext API

```python
@self.handler(events.GroupMessageReceived)
async def on_msg(event_context: context.EventContext):
    event = event_context.event
    event.launcher_id    # Group ID
    event.sender_id      # Sender ID
    event.message_chain  # MessageChain (iterate directly)

    # Reply to the current conversation
    await event_context.reply(MessageChain([Plain(text="hello")]))

    # Block default pipeline behavior
    event_context.prevent_default()

    # Block subsequent plugins
    event_context.prevent_postorder()
```

## Setting Up a Test Environment

### Deploy via Docker (GitOps + Portainer)

See `references/test-env-setup.md` for full deployment steps.

Quick summary:
1. Create `docker-compose.yaml` in `server-deploy` repo
2. Deploy via Portainer git repository method
3. Set up admin account via `/api/v1/user/init` POST
4. Configure LLM provider and model via API
5. Copy plugin to `data/plugins/` directory

### WebSocket Testing

LangBot's WebUI chat uses WebSocket. Connect to test message flow:

```
ws://<host>:<port>/api/v1/pipelines/<pipeline_uuid>/ws/connect?session_type=group
```

- `session_type=group` for group chat simulation
- `session_type=person` for private chat (always triggers pipeline)

**Requires Origin header** to pass CORS:
```javascript
const ws = new WebSocket(url, {
  headers: { Origin: 'https://your-langbot-domain' }
});
```

Send messages:
```json
{"type": "message", "message": [{"type": "Plain", "text": "hello"}]}
```

Receive:
- `{"type": "connected", ...}` — connection established
- `{"type": "user_message", "data": {...}}` — echo of sent message
- `{"type": "response", "data": {"content": "...", "is_final": true/false}}` — bot reply (streamed)

### Group Trigger Rules

Group messages only enter the pipeline if trigger rules are met:

```json
{
  "group-respond-rules": {
    "at": true,          // Respond when @bot
    "prefix": ["ai"],    // Respond to messages starting with "ai"
    "random": 0.0,       // Probability of responding to any message (0.0-1.0)
    "regexp": []         // Regex patterns
  }
}
```

For testing, set `random: 1.0` via PUT `/api/v1/pipelines/<uuid>` to respond to all messages.

**Important:** EventListener hooks like `GroupMessageReceived` fire regardless of trigger rules. Only the LLM processing (`GroupNormalMessageReceived` and beyond) requires trigger rules.

### Plugin Hot-Reload

There is **no hot-reload**. After changing plugin files:

```bash
docker restart <runtime-container>
# Wait ~5 seconds for plugin to re-mount
```

The main LangBot container does NOT need restart for plugin changes — only the runtime container.

## API Quick Reference

### Admin Setup

```bash
# Initialize admin account (first time only)
curl -X POST $BASE/api/v1/user/init \
  -H "Content-Type: application/json" \
  -d '{"user":"admin@test.com","password":"test123"}'

# Login
curl -X POST $BASE/api/v1/user/auth \
  -H "Content-Type: application/json" \
  -d '{"user":"admin@test.com","password":"test123"}'
# Returns: {"data":{"token":"eyJ..."}}
```

### Provider & Model Setup

```bash
# Create provider
curl -X POST $BASE/api/v1/provider/providers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"MyProvider","requester":"new-api-chat-completions","base_url":"https://api.example.com/v1","api_keys":["sk-xxx"]}'

# Create LLM model
curl -X POST $BASE/api/v1/provider/models/llm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"gpt-4o-mini","provider_uuid":"<uuid>","abilities":["chat","tool-use"]}'

# List models
curl $BASE/api/v1/provider/models/llm -H "Authorization: Bearer $TOKEN"
```

### Pipeline Config

```bash
# Get pipeline
curl $BASE/api/v1/pipelines -H "Authorization: Bearer $TOKEN"

# Update pipeline (e.g., set model, modify trigger rules)
curl -X PUT $BASE/api/v1/pipelines/<uuid> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '<full pipeline JSON>'
```

## Plugin Config Types

Supported `type` values in `manifest.yaml` `spec.config`:

| Type | Description | Value |
|---|---|---|
| `string` | Text input | string |
| `int` / `integer` | Number input | int |
| `float` | Decimal input | float |
| `bool` / `boolean` | Toggle | bool |
| `select` | Dropdown (needs `options`) | string |
| `prompt-editor` | Multi-line prompt editor | string |
| `llm-model-selector` | LLM model picker UI | UUID string |
| `bot-selector` | Bot picker UI | UUID string |

Example — let users choose which model the plugin uses:

```yaml
spec:
  config:
    - name: model
      type: llm-model-selector
      label:
        en_US: 'LLM Model'
        zh_Hans: 'LLM 模型'
      description:
        en_US: 'Select the LLM model. Falls back to first available if not set.'
        zh_Hans: '选择 LLM 模型。未设置时使用第一个可用模型。'
      required: false
```

Read config in plugin code:

```python
model_uuid = self.get_config().get("model")
```

## Container Restart Timing

After plugin file changes, **only the runtime container needs restart**:

```bash
docker restart langbot-test-runtime
# Wait ~15 seconds before testing
```

**When to restart both (runtime first, then host):**
- Added/removed Command or Tool components (host caches component lists)
- Changed `manifest.yaml` structure

```bash
docker restart langbot-test-runtime
sleep 8
docker restart langbot-test
sleep 8
```

**⚠️ Do NOT restart both simultaneously** — the host may connect before plugins are mounted, causing 502 errors or missing plugin registrations.

## Debugging Checklist

When a plugin doesn't work:

1. **Check runtime logs**: `docker logs <runtime-container>` — look for mount/init errors
2. **Check host logs**: `docker logs <langbot-container>` — look for pipeline processing errors
3. **Verify plugin loaded**: `GET /api/v1/plugins` — should list your plugin
4. **Test person mode first**: `session_type=person` always triggers pipeline, isolating trigger rule issues
5. **Check trigger rules**: Group mode requires @bot, prefix match, or random% to enter pipeline
6. **Verify model configured**: Pipeline's `config.ai.runner_config[config.ai.runner.id].model.primary` must point to a valid model UUID with working API keys

## Publishing Plugins

After testing, publish via `lbp publish`:

```bash
cd /path/to/MyPlugin
lbp publish
```

This builds `.lbpkg` and uploads to Space marketplace as a draft. Then go to https://space.langbot.app/market to upload screenshots and submit for review.

**Prerequisite:** Must be logged in via `lbp login --token lbpat_xxx` (PAT from Space profile page).

## Reference: EventListener-Only Plugin Pattern

For plugins that react to messages without commands or tools (e.g., auto-summarize URLs, collect messages, translate):

```
MyPlugin/
├── manifest.yaml       # Only EventListener in spec.components
├── main.py             # BasePlugin with shared logic (fetch, LLM calls)
├── components/
│   └── event_listener/
│       ├── detector.yaml
│       └── detector.py
└── requirements.txt
```

**manifest.yaml** — only declare EventListener:
```yaml
spec:
  components:
    EventListener:
      fromDirs:
      - path: components/event_listener/
```

**detector.py** — hook `*MessageReceived`, extract text, process, reply:
```python
@self.handler(events.PersonMessageReceived)
async def on_msg(event_context: context.EventContext):
    event = event_context.event
    text_parts = []
    for component in event.message_chain:
        if isinstance(component, platform_message.Plain):
            text_parts.append(component.text)
    text = "".join(text_parts).strip()
    
    if should_handle(text):
        event_context.prevent_default()
        event_context.prevent_postorder()
        result = await self.plugin.process(text)
        await event_context.reply(platform_message.MessageChain([
            platform_message.Plain(text=result)
        ]))
```

**Key:** Access shared plugin logic via `self.plugin` (the BasePlugin instance).

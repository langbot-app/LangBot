# SDK Pitfalls and Patterns

Verified gotchas for `langbot-plugin` SDK code. Canonical API docs: `docs/en/plugin/dev/`.

## Pitfalls

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

## EventListener-Only Plugin Pattern

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

# Testing Plugins Against a Running LangBot

For deployment use the `langbot-deploy` skill or `docker/docker-compose.yaml`; for instance setup (models, pipelines, bots) use the `langbot-mcp-ops` skill instead of raw HTTP.

## WebSocket Testing

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

## Group Trigger Rules

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

## Plugin Hot-Reload

There is **no hot-reload**. After changing plugin files:

```bash
docker restart <runtime-container>
# Wait ~5 seconds for plugin to re-mount
```

The main LangBot container does NOT need restart for plugin changes — only the runtime container.

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

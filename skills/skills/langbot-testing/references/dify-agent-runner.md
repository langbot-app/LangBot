# Dify AgentRunner

Use this reference when validating `langbot-team/DifyAgent` through LangBot WebUI.

## Prepare Dify

- Use a Dify Service API key from the target Dify app. Do not print the key in reports.
- For Dify Agent Chat apps, configure LangBot `app-type` as `agent`.
- Dify Agent Chat Service API may reject direct `blocking` mode with `Agent Chat App does not support blocking mode`; use streaming for direct diagnostics.

## LangBot Configuration

1. Open `LANGBOT_FRONTEND_URL`.
2. Navigate to `Pipelines` and open the target pipeline.
3. Open `Configuration > AI`.
4. Select runner `Dify`.
5. Configure:
   - `Base URL`: usually `https://api.dify.ai/v1`
   - `App Type`: `Agent` for Dify Agent Chat apps
   - `API Key`: Dify Service API key
   - `Base Prompt`: short neutral prompt unless the case needs a specific prompt
   - `Timeout`: at least `60` when testing through proxies
6. Save before using Debug Chat.

## Debug Chat Check

Send a prompt with a unique sentinel:

```text
Reply exactly with LANGBOT_DIFY_<date_or_random> and nothing else.
```

Pass only when:

- UI shows a `Bot` message containing the sentinel.
- WebSocket history or DOM inspection confirms the sentinel is in an assistant/bot message, not only in the user message.
- Backend logs show the request completed, for example `HTTP Request: POST https://api.dify.ai/v1/chat-messages "HTTP/1.1 200 OK"` and `Conversation(0) Streaming completed`.

## Diagnostics

- `GET /api/v1/pipelines/{uuid}` can confirm the saved runner id is `plugin:langbot-team/DifyAgent/default` and runner config contains `app-type`, `base-url`, and `api-key`.
- Direct Dify streaming API calls are useful only to distinguish invalid Dify credentials from LangBot runner issues.
- If Debug Chat returns `Agent runner execution failed`, inspect backend logs before changing UI settings.

## Known Failure Signatures

- `AttributeError: 'ActorContext' object has no attribute 'type'`: runner code is reading old actor fields; see troubleshooting `agent-runner-actor-context-fields`.
- Multiple runner options display as `默认`: component labels are ambiguous; see troubleshooting `ambiguous-runner-default-label`.

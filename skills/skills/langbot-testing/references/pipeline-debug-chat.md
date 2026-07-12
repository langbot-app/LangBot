# Pipeline Debug Chat

## Goal

Verify that a pipeline can receive a private debug message and return a bot response through the configured frontend.

## Path

1. Open `LANGBOT_FRONTEND_URL` from `skills/.env` or the active user-provided environment.
2. Navigate to `Pipelines`.
3. Open the target pipeline.
4. Select `Debug Chat`.
5. Send a short deterministic prompt, for example:

   ```text
   请只回复 OK，用于前端调试测试。
   ```

## Success Criteria

The UI should show:

- A `User` message containing the prompt.
- A `Bot` message containing the expected response, for example `OK`.

When the prompt itself contains a sentinel token, do not treat `document.body` containing that token as success. Confirm the token appears in a `Bot`/assistant message, WebSocket history entry, or backend completion log.

For `scripts/e2e/pipeline-debug-chat.mjs`, inspect
`automation-result.json` when a sentinel is present in the prompt. A pass should
show the expected text in a new assistant message; the
`after_assistant_expected_count` value must increase beyond
`before_assistant_expected_count`. If only the user prompt contains the
sentinel, the run is a failure even when the page body contains enough total
occurrences.

The backend log should include:

```text
Processing request from person_websocket...
Streaming completed
```

## Failure Criteria

Treat the test as failed if:

- Only the user message appears.
- The page shows `Agent runner temporarily unavailable`.
- Backend logs contain `All models failed during streaming setup`.
- Backend logs contain `Action invoke_llm_stream call timed out`.
- Backend logs contain `Action list_plugins call timed out`.

When failures match these signatures, read `troubleshooting.md`.

# Model Provider Testing

## Goal

Verify that a model provider can be added, configured with a key, and tested from the WebUI.

## Rules

- Never print the API key or token value.
- Prefer using a test key supplied through the user's environment or secret manager.
- After saving a provider, use the WebUI test button when available.
- Confirm the provider is usable by running a small pipeline Debug Chat test, not only by checking that the form saved.

## DeepSeek Flow

1. Open `LANGBOT_FRONTEND_URL` from `skills/.env` or the active user-provided environment.
2. Go to `Models`.
3. Add or edit a DeepSeek provider.
4. Fill the required base URL, API key, and model fields according to the current UI.
5. Click the provider/model test button.
6. If the UI test succeeds, verify with a pipeline Debug Chat message.

## Completion Signal

Report the provider name, model name, UI test result, and pipeline Debug Chat result. Do not include secrets.

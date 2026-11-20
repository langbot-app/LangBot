# Legacy adapters (frozen)

The single-file adapters in this directory are **legacy and no longer updated**.

- Do not modify, fix or extend anything here, and do not add new adapters to this directory.
- New platform adapters and all adapter work go into `src/langbot/pkg/platform/adapters/<platform>/` (event-based adapter layout: `adapter.py`, `event_converter.py`, `message_converter.py`, `api_impl.py`, `platform_api.py`, `types.py`, `errors.py`, `manifest.yaml`). If a platform only exists here, port it to `adapters/` instead of patching it.
- References: `dev-docs/event-based-agents/03-adapter-structure.md`, `01-event-system.md`, `02-platform-api.md`, and `dev-docs/event-based-agents/adapters/acceptance-checklist.md`.

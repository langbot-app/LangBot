---
name: langbot-plugin-dev
description: Develop, debug, test, and publish LangBot plugins. Use when creating or fixing a LangBot plugin or official plugin under plugins/, choosing component types (EventListener, Command, Tool, Runner, KnowledgeEngine, KnowledgeRetriever, Parser, Page), calling the Workspace API, platform API or execution APIs from a plugin, persisting plugin data (storage APIs, never the filesystem), declaring plugin permissions, debugging with lbp run, or publishing to LangBot Space. Triggers on "langbot plugin", "lbp", "plugin permissions", "workspace api", "call_platform_api", "plugin debug".
---

# LangBot Plugin Development

## Sources of Truth

| Need | Where |
| --- | --- |
| Author docs (canonical) | `docs/en/plugin/dev/` (also `zh`, `ja`): `tutor`, `basic-info`, `directory-structure`, `permissions`, `components/*`, `apis/*`, `publish/*` |
| SDK, `lbp` CLI, Plugin Runtime | `sdk/` in the LangBot repo (`langbot_plugin`, PyPI `langbot-plugin`); release rules in `sdk/RELEASING.md` |
| Working examples | `plugins/` in the LangBot repo, indexed by `plugins/catalog.json`; minimal: `plugins/misc/HelloPlugin`; full Runner: `plugins/Runner/LocalAgent` |
| Official plugin rules | `plugins/AGENTS.md`, `plugins/RELEASING.md` |
| Runtime debugging | `docs/en/develop/plugin-runtime.mdx` |

Read the matching doc page before writing code; do not guess SDK signatures.

## Components

Declare components in `manifest.yaml` `spec.components`; each component has a `.yaml` (metadata) and a `.py` (implementation). Docs per type in `docs/en/plugin/dev/components/`:

- `EventListener`: hook pipeline events (`*MessageReceived`, `*NormalMessageReceived`, `NormalMessageResponded`, ...).
- `Command`: `!command` handlers. `Tool`: LLM function-call tools.
- `Runner`: an Agent runner/event processor (see LocalAgent and other `plugins/Runner/*`).
- `KnowledgeEngine`, `KnowledgeRetriever`, `Parser`: RAG backends, retrieval and document parsing.
- `Page`: plugin-provided WebUI pages.

## API Surfaces

| Surface | Call | Docs |
| --- | --- | --- |
| Common plugin APIs (models, storage, bots, messages) | `self.plugin.invoke_llm(...)`, `self.plugin.send_message(...)`, ... | `apis/common.mdx`, `apis/messages.mdx`, `apis/llm-requests.mdx` |
| Pipeline event context | `event_context.reply(...)`, `prevent_default()` | `apis/pipeline-events.mdx` |
| Platform API | `self.plugin.call_platform_api(bot_uuid, action, params)`; standard actions first, adapter-specific actions via `action="call_platform_api"` | `apis/platform.mdx` |
| Workspace API (Unified API) | `self.plugin.workspace.<domain>.<op>(...)` or `self.plugin.workspace.call("<op.id>", ...)`; Runners use `ctx.api.workspace` | `apis/workspace.mdx` |
| Runner context | `ctx.api`, `ctx.resources` | `apis/agent-run.mdx`, `components/runner.mdx` |

Workspace API rules:

- Operations share IDs with LangBot's HTTP API, MCP and Workspace assistant (for example `pipeline.list`, `knowledge.base.retrieve`). The full list with risk levels is in `apis/workspace.mdx`; `await self.plugin.workspace.list()` returns the operations granted to this installation at runtime.
- Calls return `{"ok": True, "result": ...}` or `{"ok": False, "error": {"code": ...}}`; check `ok`. Treat `permission_denied` as expected and explain what is missing.
- A Runner that offers Workspace operations to a model must offer only `ctx.resources.workspace_operations`; none when it is empty.

## Persistence

Plugins must not write data they need to keep to the filesystem: no files under the plugin directory, `data/` or the working directory, and no self-managed SQLite/JSON stores. The Plugin Runtime's disk is not persistent (the plugin directory is replaced on upgrade or reinstall, and the Runtime may be a separate container or host), and local files are neither isolated per Workspace nor backed up. Everything that must persist goes through the APIs into Core's persistent database:

- Plugin-private state: `self.plugin.set_plugin_storage` / `get_plugin_storage` / `get_plugin_storage_keys` / `delete_plugin_storage` (capability `storage.plugin`).
- Data shared between plugins: the `*_workspace_storage` equivalents (capability `storage.workspace`).
- Runner state: `ctx.state_get` / `ctx.state_set` with scope `conversation`, `actor`, `subject` or `runner`.
- Vectors: `vector_upsert` / `vector_search` / `vector_delete`. User-uploaded config files: `get_config_file`.

Values are bytes (serialize JSON yourself) and limited to 10 MiB each by default. Only scratch files may touch disk, through `tempfile`, deleted within the same call. When fixing or reviewing a plugin, treat `open(..., "w")`, `Path.write_*`, `sqlite3` and similar on non-temp paths as a bug and migrate it to the storage APIs. Details: "Persistence Rules" in `apis/common.mdx`.

## Permissions

Declare installation permissions in the plugin manifest `spec.permissions` (`workspace_operations` and `capabilities`). Request the minimum; high-risk operations are flagged to the confirming member. Runner component permissions do not accept workspace operation grants. An empty declaration denies global access; an absent declaration uses legacy compatibility mode and never grants Workspace operations. New installs, and permissions added by an upgrade, need member confirmation in WebUI; an API key cannot grant permissions. Details: `docs/en/plugin/dev/permissions.mdx`.

## Workflow

```bash
lbp init MyPlugin        # scaffold (includes a GitHub release workflow)
cd MyPlugin
cp .env.example .env     # DEBUG_RUNTIME_WS_URL + PLUGIN_DEBUG_KEY from WebUI: Extensions -> Debug Info
lbp run                  # attach to a running LangBot's Plugin Runtime
lbp build                # package .lbpkg
lbp login && lbp publish # upload to LangBot Space as a draft
```

The debug key is per Workspace and rotates every two hours. For test traffic, prefer Debug Chat or the pipeline WebSocket in `references/testing.md`; drive instance setup through the `langbot-mcp-ops` skill.

For official plugins under `plugins/`, keep each plugin's dependencies and tests independent, regenerate `plugins/catalog.json` with `python plugins/scripts/check_catalog.py --write`, and never add plugin dependencies to Core.

## Marketplace README and i18n

- Root `README.md` MUST be English (default and fallback on LangBot Space).
- Other languages go in `readme/README_{lang}.md` for `zh_Hans`, `zh_Hant`, `ja_JP`, `th_TH`, `vi_VN`, `es_ES`, `ru_RU`.
- `manifest.yaml` `metadata.label` / `metadata.description` carry the same eight locales; `repository` must be a live URL. The marketplace syncs from the manifest: edit and re-publish instead of patching live data.

## References

- `references/sdk-pitfalls.md`: verified SDK gotchas (MessageChain iteration, `invoke_llm` arguments, `prevent_default` vs `prevent_postorder`, component YAML shape, import paths), pipeline event table, config field types, EventListener-only pattern.
- `references/testing.md`: pipeline WebSocket testing, group trigger rules, restart timing, debugging checklist.

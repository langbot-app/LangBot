# Scenario packs (format version 1)

A scenario is a data-only JSON template for one bot and its referenced Pipelines,
Agents and event processors. The bot page exposes export, preview, import and a
persistent setup checklist. Imported bots are disabled.

## Sharing and setup

1. Choose **Export scenario** and follow the five Workspace-resource steps: existing message-platform bot, Pipelines, Agents, installed plugins/event processors/MCP servers, and knowledge bases. No Marketplace catalog is used for export. Existing routes to selected targets are preserved; extra resources do not create implicit routes. Review the JSON, enter recipient
   instructions and download the `.langbot-scene.json` file.
2. In another Workspace, choose **Import scenario**, select the file and review
   the required fields before confirming.
3. Follow configuration links to enter platform credentials, select models and
   initialize the imported empty knowledge bases. Missing plugins are installed automatically from Marketplace; existing plugins and their configuration are preserved.
4. Save configuration, return to the bot and select **Check configuration**.
5. Complete external platform subscriptions and enable the bot in its settings.

Knowledge-base names, descriptions, creation/retrieval settings and engine dependencies are included. Contents, source files, indexes and collection identifiers are
never included. Imported knowledge bases receive fresh collections and remain uninitialized until their settings are saved. MCP configuration is copied with fresh names and UUIDs; imported MCP servers remain disabled. Plugin configuration defaults are applied only to newly installed plugins. Knowledge-engine plugin IDs are dependencies; recipients supply
their own knowledge resources. Filled fields are not successful connection tests.

Structured credentials are removed. Unknown configuration fields are cleared
and exposed as setup requirements. Prompt editor content and author descriptions
are portable text and must be reviewed before sharing. Plugin installation and
Workspace-wide plugin configuration use the existing plugin management UI.

## API

All endpoints require `resource.manage` and are Workspace scoped:

| Method | Path | Body / result |
| --- | --- | --- |
| POST | `/api/v1/scenarios/export/<bot_uuid>` | Optional metadata, or `{metadata, selection}`; returns package |
| POST | `/api/v1/scenarios/preview` | Package; returns normalized package and dependency status |
| POST | `/api/v1/scenarios/import` | `{package, request_id}`; request ID is a UUID |
| GET | `/api/v1/scenarios` | `{imports: [...]}` with current setup reports |
| GET | `/api/v1/scenarios/<import_id>` | Current setup report |

Reuse `request_id` for retries of one import; use a new ID for a separate copy.
Plugin installation completes before resource creation and is not held inside the resource transaction. Successfully installed plugins remain available if a later installation or resource creation fails; retries reuse them. Creation and import metadata are written in one tenant transaction. Imported
resources receive fresh UUIDs; internal references are remapped. Existing resource
configuration is never overwritten. Import records reuse `WorkspaceMetadata`
under `scenario_import:<request_id>` and do not store subsequently entered secrets.

The API is additive; existing `lbctl` resource endpoints retain their contracts.
No dedicated `lbctl` command is introduced in this repository.

## Current boundaries

- Runner compatibility currently uses exact exported versions, not semver ranges.
- Missing plugins are installed automatically from Marketplace using declared versions. Already installed incompatible versions are reported without silently upgrading or downgrading shared Workspace configuration. Unpublished/debug-only dependencies must be made available before importing.
- Knowledge-engine plugins are installed automatically; readiness of their remote
  services is not probed by the scenario service.
- Free-text credential detection, package editing, automatic external-platform
  setup and cross-resource connection tests are not implemented.
- Selected plugin bindings and MCP server references are rebuilt. Broad source Workspace grants are not copied. Skill and MCP resource bindings still require recipient configuration.
- Imported Pipelines are loaded when the bot is enabled or their configuration is
  saved. The checklist records field completeness, not a runtime health guarantee.

## Verification

Run in Linux to match CI:

```sh
uv run pytest tests/unit_tests/test_scenario_format.py tests/unit_tests/test_scenario_service.py -q
```

The tests cover projection of credentials and resource references, package graph
validation, actual SQLite creation, disabled state, ID remapping, retry deduplication
and Workspace-scoped import-record lookup. Full two-instance platform/plugin smoke
testing is still required before release.

## Export selection

`export_scenario(bot_uuid, metadata, selection)` accepts an optional object with
`pipeline_uuids`, `agent_uuids`, `event_processor_uuids`, `plugin_ids`,
`mcp_server_uuids`, and `knowledge_base_uuids` arrays. IDs must belong to the current
Workspace. Unselected knowledge references become setup requirements. Required
Runner plugins are included automatically. Omitting selection retains automatic
collection of the bot graph for existing API clients.

The browser import request allows time for dependency downloads. Credentials stay
empty and the imported bot must pass its setup checklist before activation.

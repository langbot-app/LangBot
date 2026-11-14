# Sharing content to LangBot Space (LANG-439)

Core lets members share Workspace content to LangBot Space and use the Space prompt library. Space owns review and publication; Core only packages, redacts and forwards.

## Core surface

`/api/v1/space-share/*` (`pkg/api/http/controller/groups/space_share.py`, helpers in `pkg/api/http/service/space_share.py`):

| Route | Purpose |
| --- | --- |
| `GET /context` | Bound LangBot Account and creator slug |
| `GET /prompts/library`, `POST /prompts/library/<a>/<n>/use` | Proxy of the public Space prompt library |
| `GET /prompts/favorites`, `PUT/DELETE /prompts/favorites/<a>/<n>` | Favorites of the bound account (requesting member first, then the Workspace owner) |
| `POST /prompts/preview`, `POST /prompts` | Validate / submit a prompt (`kind`: `messaging` or `agent`) |
| `GET /skills/<name>/preview`, `POST /skills/<name>` | File list + credential scan / submit the current skill revision |
| `POST /mcp/<name>/preview`, `POST /mcp/<name>` | Redacted remote MCP config / submit it |
| `GET /submissions` | The account's content submissions on Space |

Locally installed or GitHub-installed plugins reuse `/plugins/<a>/<n>/space-upload`; the shared archive is the exact persisted installation artifact (`PluginRuntimeConnector.get_installed_plugin_package`), so overrides and GitHub sync do not apply.

## Rules

- Credentials never leave Core. Remote MCP headers, URL query parameters and path segments whose key or value looks like a credential become `${VAR}` placeholders declared in `required_inputs`; a final scan refuses anything that still looks like a secret. stdio MCP servers cannot be shared (first phase).
- Prompts and skills are scanned for credentials (block) and personal/internal data (requires `acknowledge_warnings`).
- Marketplace MCP installs with `required_inputs` are created disabled; `GET /api/v1/mcp/servers/<name>` reports `unfilled_inputs` (names only) so the WebUI can ask for values.
- The Prompt editor shows the library/share toolbar only when the form passes `systemContext.prompt_library_kind` (`messaging` from Pipelines, `agent` from Agents).

## Space contract

`POST /api/v1/marketplace/content-submissions` (multipart `item_type`, `metadata` JSON incl. `payload`, optional skill `file`). Space validates again, stores the artifact, and dispatches `content-review-request-v1` on the plugin review webhook. Verdicts are `content-review-verdict-v1` signed with the plugin reviewer keys. A passed prompt publishes immediately; skills/MCPs publish for whitelisted submitters or after admin approval; a failed review rejects with the report summary. See the langbot-space repository for details.

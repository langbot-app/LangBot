# Backend message language

Workspace settings expose one **Workspace language**, independent of each member's
WebUI language. It selects LangBot-owned API business errors, model error prefixes,
Pipeline default notices and international platform replies. Supported locales are
`en_US`, `zh_Hans`, `zh_Hant`, `ja_JP`, `es_ES`, `ru_RU`, `th_TH` and `vi_VN`.
Workspaces without a setting default to English. Existing custom messages and
historical records are not rewritten.

## Storage and boundaries

`pkg/i18n/workspace.py` stores `message_language` in existing `WorkspaceMetadata`;
no database migration or instance-wide configuration is needed. Reads and writes
use tenant-scoped units of work. GET/PUT `/api/v1/workspaces/current/language`
require `workspace.view` / `workspace.update`; matching MCP tools are
`get_workspace_message_language` and `set_workspace_message_language`.

An authenticated Workspace takes precedence over the browser's
`X-LangBot-Language` header. The header supplies presentation language only for
account-only or unauthenticated responses and never selects a tenant. HTTP, MCP,
Pipeline and adapter boundaries set a ContextVar so concurrent Workspaces do not
share a language. Adapter SDK thread callbacks use their owning bot's cached
Workspace language, never the calling request's language.

The per-application cache holds at most 256 Workspaces for 30 seconds. Local
writes update the cache immediately; other processes refresh at the next async
message/request boundary after expiry. A running operation keeps its selected
language. Synchronous SDK callbacks use the most recently loaded value.

## Pipeline overrides

The output `misc` section accepts these optional string settings:

| Setting | Default purpose | Placeholder |
| --- | --- | --- |
| `failure-hint` | Request/runner execution failure | none |
| `rate-limit-hint` | Rate limit reached | none |
| `content-filter-hint` | Message rejected by content filter | none |
| `content-filter-error-hint` | Content check failed | none |
| `tool-call-hint` | Tool call notification | `{tools}` |
| `runner-not-found-hint` | Configured runner missing | `{runner}` |
| `runner-not-authorized-hint` | Runner authorization failure | none |
| `runner-unavailable-hint` | Runner temporarily unavailable | none |

Blank values inherit the Workspace translation. Custom text is emitted literally
with only the documented placeholder replaced. The previous shipped
`failure-hint` value `Request failed.` also inherits language; this avoids a data
migration. Existing output switches (including tool-call visibility and exception
handling) retain their behavior.

## Adding messages

Use `pkg.i18n.t()` with a stable English template and named parameters. Add the
same key and placeholders to all eight JSON catalogs. The catalog parity test
checks completeness and formatting. `pipeline_notice()` handles configurable
notices. Exact aliases at the API response boundary cover legacy business wording;
do not add substring replacement of arbitrary error text.

China-only adapters, field validation diagnostics, raw provider/plugin errors,
tracebacks, protocol values and machine-readable status codes are outside this
translation layer. Their values remain useful for diagnostics and interoperability.
Model errors translate LangBot's category/prefix while retaining upstream detail.
Plugin-authored content must use the plugin's own localization. System prompts and
user-authored content are not translated.

Locale JSON files are included in Python package data. Focused coverage lives in
`tests/unit_tests/test_backend_i18n.py`, the Workspace HTTP integration tests and
`web/tests/e2e/workspace-language.spec.ts`.

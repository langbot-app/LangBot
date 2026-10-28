# WeKnora Agent

`agent-id` is optional in both modes. When omitted, `chat` uses `builtin-quick-answer` and `agent` uses `builtin-smart-reasoning`; an explicit empty value omits the provider ID. Explicit saved IDs are never replaced. `knowledge-base-ids` are remote WeKnora IDs in both modes, not LangBot knowledge base UUIDs.

## Overview

Run a WeKnora agent or knowledge-base chat app as a LangBot Runner.

## Package information

- **Runner ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **Version**: `0.1.2`
- **Repository**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## Capabilities

- **Enabled**: `streaming`
- **Not declared**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## Configuration

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `base-url` | `string` | Yes | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | Yes | Empty |
| `app-type` | `select` | Yes | `agent` |
| `agent-id` | `string` | No | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | No | `[]` |
| `web-search-enabled` | `boolean` | No | false |
| `advanced-settings` | `boolean` | No | false |
| `timeout` | `integer` | No | `120` |
| `base-prompt` | `string` | No | `请回答用户的问题。` |

## Host permissions

- **`storage`**: `plugin`

## Installation and usage

1. Install the plugin from the LangBot plugin marketplace.
2. Select the Runner ID below in the Pipeline Runner selector.
3. Fill in connection settings from the table and store credentials in secret fields in the admin UI.

## Security and limitations

- The runner can use only LangBot resources authorized for the current run.
- Availability, model abilities, and rate limits depend on the external service.
- See the full Chinese README at the package root for advanced behavior and product-specific limitations.


## SDK 0.6.1 shared-runtime candidate

See [shared-runtime boundaries and upgrade notes](SHARED_RUNTIME.md) before upgrading.

# DeerFlow Agent

Credentials and provider identifiers are opaque: `api-key`, `auth-header`, `assistant-id`, and `model-name` keep explicit whitespace and empty values. A nonempty `auth-header` overrides Bearer `api-key`. Invalid string/boolean/integer types fail with a field-only configuration error rather than being substituted.

## Overview

Run a DeerFlow LangGraph agent as a LangBot Runner.

## Package information

- **Runner ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **Version**: `0.1.2`
- **Repository**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## Capabilities

- **Enabled**: `streaming`, `multimodal input`
- **Not declared**: `tool calling`, `knowledge retrieval`, `interrupt`

## Configuration

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `api-base` | `string` | Yes | `http://127.0.0.1:2026` |
| `api-key` | `secret` | No | Empty |
| `auth-header` | `secret` | No | Empty |
| `assistant-id` | `string` | Yes | `lead_agent` |
| `advanced-settings` | `boolean` | No | false |
| `model-name` | `string` | No | Empty |
| `thinking-enabled` | `boolean` | No | false |
| `plan-mode` | `boolean` | No | false |
| `subagent-enabled` | `boolean` | No | false |
| `max-concurrent-subagents` | `integer` | No | `3` |
| `timeout` | `integer` | No | `300` |
| `recursion-limit` | `integer` | No | `1000` |

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

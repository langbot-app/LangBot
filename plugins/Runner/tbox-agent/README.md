# Tbox Agent

`remove-think` is a strict boolean (default `false`). Set it to `true` to hide reasoning fields and `<think>` blocks, including split streaming delimiters; answer text and tool-call content are preserved.

## Overview

Run an Ant Tbox application as a LangBot Runner.

## Package information

- **Runner ID**: `plugin:langbot-team/TboxAgent/default`
- **Version**: `0.1.0`
- **Repository**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent)

## Capabilities

- **Enabled**: `streaming`, `multimodal input`
- **Not declared**: `tool calling`, `knowledge retrieval`, `interrupt`

## Configuration

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `api-key` | `secret` | Yes | Empty |
| `app-id` | `string` | Yes | Empty |
| `timeout` | `number` | No | `120` |

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

## Native migration notes

Reasoning suppression applies to streaming `thinking` and non-streaming `reasoningContent`. The default remains to show reasoning. Streaming selection follows the delivery capability unless explicitly overridden. Provider conversations remain in scoped `external.conversation_id` state. Native `user_id=bot_uuid` and plugin actor-based user IDs are not equivalent; migration must resolve this separately.

`timeout` defaults to 120 seconds and must be finite and positive. Generated text (including hidden reasoning) is limited to 1 MiB characters; Coze and Tbox uploads are limited to 10 MiB per file. Existing remote conversation IDs require an explicit scoped import or reset when migrating from native runners. These source changes do not publish or install a new plugin version.

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-bot` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-bot` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-bot` uses `conversation.bot_id` (or Host runtime `bot_id` when there is no conversation), exactly, without a prefix.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.


## Dedicated runtime placement

This release is unsigned and dedicated. Historical shared-runtime notes in [SHARED_RUNTIME.md](SHARED_RUNTIME.md) do not grant shared-worker eligibility.

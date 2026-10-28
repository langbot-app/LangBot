# PowerContext for LangBot

Connects LangBot to a running [PowerContext](https://github.com/oceanbase/powercontext) Server. The plugin keeps
PowerContext as the source of truth and adds LangBot-native context injection, Source capture, tools, and diagnostics.

## Features

- Resolves a durable PowerContext Scope from a fixed Scope ID or a hashed LangBot session, speaker, or bot binding.
- Calls `POST /v1/context/prepare` before a model request and injects only the bounded returned context.
- Captures the current normal user turn through `POST /v1/sources/content` after recall, avoiding self-recall.
- Provides `powercontext_remember`, `powercontext_recall`, and `powercontext_forget` tools.
- Provides `!powercontext` and `!powercontext health` diagnostics.
- Lets an administrator explicitly bind or clear the current identity with `!powercontext bind <scope_id>` and
  `!powercontext clear`.
- Fails open: a PowerContext outage does not block the normal LangBot response path.

This plugin does not embed PowerContext, start its Server, or duplicate its storage and retrieval behavior.

## Requirements

- LangBot with the Plugin Runtime enabled.
- A running PowerContext Server. PowerContext 1.0.0 or a compatible current build is recommended.
- A PowerContext Scope that the configured bearer identity can read and contribute to.

Start a local basic-memory Server by following the upstream setup:

```bash
uv tool install --force "powercontext[cli,server]==1.0.0"
mkdir -p powercontext-config && cd powercontext-config
powercontext config init --language en --output .env
powercontext server run --env-file .env
```

## Configuration

Set `server_url` and, when Server authentication is enabled, `api_token`. The token belongs to this installation:
it is read only from the installation's own configuration and never from a process environment variable, so a shared
worker cannot send one installation's process credential to another installation's Server. Loopback HTTP is accepted.
A remote HTTP URL is rejected unless `allow_insecure_http` is explicitly enabled; use HTTPS for persistent or
multi-user deployments.

Choose one Scope setup:

1. Set `scope_id` to a Scope selected by the operator; or
2. Leave `scope_id` empty, choose `scope_mode`, and have a LangBot administrator run:

   ```text
   !powercontext bind <existing-powercontext-scope-id>
   ```

`allow_default_scope` is disabled by default. Enabling it makes unbound chats use the PowerContext Server's default
Scope and can mix context between chats if that default is shared.

Scope binding identities are SHA-256 digests. Raw LangBot bot, session, and sender IDs are not sent as binding keys.
`speaker` mode requires a sender ID. Binding changes require LangBot administrator privilege and PowerContext
`server.admin` authorization.

## Context and memory behavior

On `PromptPreProcessing`, the plugin resolves exactly one Scope, prepares historical context using the current user
message, and appends it as a system message with an explicit untrusted-history boundary. It then captures the user turn
as an independent Source. The latest bridge state is also published to the query variable `_powercontext_context` for
diagnostics and compatible plugins.

Automatic Source capture is not an explicit Memory write. PowerContext may process Sources according to its configured
runtime. Explicit durable Memory writes occur only through `powercontext_remember`.

Search results preserve their immutable citation. `powercontext_forget` requires that complete citation and retires the
entry without deleting its revision history.

## Security notes

- Historical context is data, not an instruction override.
- Do not put credentials or secrets into Memory.
- Set `api_token` in this installation's own configuration; the plugin never reads a bearer token from the process
  environment. Restrict access to plugin configuration because LangBot currently stores `api_token` as a string setting.
- Keep `allow_default_scope` off in multi-chat deployments unless sharing is intentional.
- Prefer HTTPS for a remote Server; HTTP exposes content and bearer credentials in transit.

## Commands

```text
!powercontext
!powercontext health
!powercontext bind <scope_id>   # administrator only
!powercontext clear             # administrator only
```

## Development

```bash
python -m pytest -q
lbp build
```

The HTTP contract follows PowerContext's checked-in `openapi/powercontext.yaml` endpoints for Scope bindings, prepared
context, Source capture, and Memory operations.

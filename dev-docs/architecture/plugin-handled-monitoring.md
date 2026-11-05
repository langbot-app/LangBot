# Plugin-handled message monitoring

Status: implemented (LANG-320). Owner code: `pkg/pipeline/monitoring_helper.py`, `pkg/plugin/handler.py`.

## Problem

An EventListener can take a message over with `prevent_default()` and answer through
`ctx.reply`, `self.plugin.send_message` and `self.plugin.invoke_llm`. Before this change the
user message was recorded with the pipeline Runner as `runner_name` although no run happened,
plugin replies and send failures were not recorded, and plugin-level LLM calls crashed the
monitoring writer (`'Query' object has no attribute 'launcher_type'`).

## Contract

`monitoring_messages.handled_by` (migration `0045_monitoring_handled_by`, nullable, indexed):

| Value | Meaning |
| --- | --- |
| `runner:<runner_id>` | The pipeline handed the message to its Runner. |
| `plugin:<author>/<name>` | That plugin prevented the default processing. |
| `plugin:unknown` | A plugin prevented it, but the Runtime could not say which. |
| `NULL` | Legacy rows, or messages stopped before processing (rules, rate limit, ...). |

Writers:

- `mark_handled_by()` / `mark_plugin_handled()` keep the value in the Query variable
  `_monitoring_handled_by`. `MonitoringHelper.finish_query()` writes it to the user message.
  For plugin handlers it also clears `runner_name`.
- `REPLY_MESSAGE` records each `ctx.reply` as an `assistant` row whose parent is the user message.
  A failure records the row as `error` plus a `PluginReplyError`, then re-raises unchanged.
- `SEND_MESSAGE` records an `assistant` row in session `<target_type>_<target_id>`. A failure
  records `PluginSendError`. With a resolvable origin the row is linked to the triggering message.
- Plugin-level `INVOKE_LLM` / `INVOKE_LLM_STREAM` run on a Host-built Query labelled with the
  plugin (`_monitoring_plugin`). With a resolvable origin, `attribute_to_origin()` copies only the
  monitoring identity (bot, pipeline, session, message id) and never pipeline config or resources.
  `details.plugin` names the caller.

Monitoring writes never change delivery: recording errors are logged and swallowed.

## Attribution sources and compatibility

- **Who prevented default**: the Plugin Runtime adds a `prevent_default` entry to
  `response_sources` for the first plugin that sets the flag. Older Runtimes do not, so a
  single emitted plugin is attributed and anything else is `plugin:unknown`. Reply-source
  attribution ignores the new kind.
- **Origin of plugin actions**: Execution inputs are `extra='forbid'`, so a new payload field
  must never reach a Host that does not declare it. The Host opts in per event by adding
  `origin_attribution: true` to the emitted EventContext (`PluginRuntimeConnector.emit_event`).
  Only then does the SDK worker relay `origin_query_uuid` on plugin-level `invoke_llm`,
  `invoke_llm_stream` and `send_message`, and only while the handler runs.
  `ExecutionModelInput` / `ExecutionSendInput` accept the optional field. The Host resolves it
  with `_resolve_query`, i.e. only live Queries in the caller's own Workspace generation.
  It is used for attribution only, never for authorization.

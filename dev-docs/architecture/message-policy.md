# Bot message policy and message lifecycle

Status: implemented on `feat/message-policy` (PR #2966). User docs: `docs/*/usage/platforms/readme.mdx` (bots), `docs/*/plugin/dev/apis/pipeline-events.mdx` (message lifecycle events).

The settings around the AI (trigger, safety, general output) and plugin enablement used to live inside each pipeline, so they did nothing for bots routed to an Agent or for bot-level commands. They now live on the bot and run through one policy runtime that Chat, Agent and command delivery all call. The pipeline is called **Chat** in user-facing text; identifiers keep `pipeline` (table names, HTTP paths, MCP tool names, SDK names, `target_type: "pipeline"`, the `messaging` processor value).

## Storage

- `bots.message_policy` (JSON) uses the old pipeline key names: `trigger` (`group-respond-rules`, `access-control`, `ignore-rules`, `message-aggregation`, `misc.combine-quote-message`), `safety` (`content-filter`, `rate-limit`), `output` (`long-text-processing`, `force-delay`, `misc.*` general items) and `plugins` (`{enable_all, plugins: [{author, name}]}`). Schema, defaults and validation: `pkg/message_policy/schema.py`.
- Each `event_bindings[]` item may carry `policy`, a partial override merged over the bot policy (`resolve_policy`). Only `message.received` uses it.
- Saving a bot: an omitted route `policy` (or `policy.plugins`) keeps the stored value; explicit `null` removes it (`retain_plugin_selection`). Old WebUI/clients therefore cannot wipe migrated overrides.
- Added switches with no old equivalent: `trigger.group-respond-rules.enabled`, `safety.rate-limit.enabled`. `neutral_policy()` (admit everything, change nothing) depends on them.
- Chat configs keep the AI-specific output (`remove-think`, `track-function-calls`, tool-call / runner hints, the Cloud `daily-message-quota-exceeded` hint) and lose the moved keys. Old clients posting `trigger` / `safety` / moved `output` keys to the pipeline API are accepted; the keys are dropped (`split_legacy_config`). One conversion function serves the migration, legacy import and the pipeline API.

## Runtime

- `MessagePolicyManager` (`ap.message_policy_mgr`) compiles a `MessagePolicyRuntime` per (Workspace, bot, route id) and caches it until the bot entity changes (`invalidate_bot`). Long text, content filter and rate limit build internal state at compile time, which is why a runtime is compiled instead of only rewriting `query.pipeline_config`. The rate limiter is shared by the application; its counters are keyed per session.
- `bind_query` attaches the runtime to the entry Query and overlays the effective policy onto `query.pipeline_config` under the old keys (`overlay_policy`) so legacy plugins reading those keys keep working. The route id travels in `query.variables['_message_route_id']`; when it is missing the first route of that bot pointing at the same pipeline supplies the override.
- Call sites:
  - **Chat**: the original stages (`GroupRespondRuleCheckStage`, `BanSessionCheckStage`, content filters, rate limit, long text, `ResponseBackStage`) stay in place and order and delegate to the runtime. The pipeline command stage was removed.
  - **Commands** (`RuntimeBot._try_handle_plugin_command`): `admit()` before execution, `send_command_reply()` for output.
  - **Agent**: `admit()` before dispatch; `ReplyStreamSession` and the `event_reply` platform tool apply the outbound side. Non-streaming: outbound filter, long text, delay, @sender, quote. Streaming: delay, @sender, quote only. Proactive `send_message` is not affected.
  - **Plugin processors** (bot subscriptions) skip inbound interception; their replies use the same outbound side.
  - **Debug chat** uses `neutral_runtime()`.
- Drops are recorded with `failure_code: "message_policy"` and a reason such as `route:r1: safety.rate-limit` (`drop_reason`); monitoring shows them as ignored with the reason, and the route dry-run (`POST /api/v1/platform/bots/<uuid>/event-routes/dry-run`) previews them.

## Message lifecycle (`message.received`)

```text
RuntimeBot._begin_message
  select route (compute only)
  QueryPool.add_query(enqueue=False)          one Query per message, registered in the pool
  message_policy_mgr.bind_query
  platform notifications (MessageReceived, observe only)
  *MessageReceived                            prevent_default ends the message
  permitted system or plugin command?  admit → *CommandSent → execute → outbound
  else             admit → Chat stage chain | Agent → outbound
```

- `*MessageReceived` fires once, at the bot entry, before group response rules, including for messages a route rule discards and for every raw message when aggregation is on. Queries that enter a pipeline directly (`pipeline.run`, adapter-enqueued queries) fire it in the pipeline fallback; `_message_received_dispatched` prevents a second dispatch.
- Commands match "prefix + registered command name" before route rules, use the policy of the route the message would otherwise match (bot default when none), and do not aggregate. Hooks and commands share the entry Query, so `reply()`, `get_bot_uuid()` and query variables work.
- Enabled system names and aliases take precedence over plugin names. Permission is checked against the sender (`person_<id>`), including in groups. A silent denial resumes normal routing, never a lower-priority command. Notice mode replies without executing the command. `/help` uses the same winner and permission checks.
- `*NormalMessageReceived` and `NormalMessageResponded` run in the Chat stage chain as before and around Agent dispatch. `PromptPreProcessing` is Chat-only. On streaming replies `NormalMessageResponded` is a notification only.
- Platform notifications (`MessageDeleted`, `GroupMemberJoined`, ... via `_eba_event_to_plugin_event`) go to enabled plugins, observe only. Producing adapters: `dev-docs/event-based-agents/adapters/00-index.md`.

## Plugin enablement

- `message_policy.plugins` decides which plugins receive hooks and whose commands match (`enabled_plugins`). `None` means all. Order is the dispatch order.
- The Chat extension list only authorizes AI-callable tools. Exception: queries without a bot policy (debug chat, `pipeline.run`) bind the neutral policy and use the Chat's plugin list for hooks, as before.
- Command processors (`command_settings.processors`) only carry per-bot command configuration; the WebUI edits them as **Command settings** on a plugin's row in the bot's Plugins tab. An enabled plugin without a processor uses default config; a legacy processor bound with `enabled: false` still disables that plugin's commands. When plugins share a command name, the order of the effective plugin list (the same order hooks are dispatched in) decides the winner; with `enable_all` the Runtime's command list order applies. The WebUI keeps `plugins` sorted in list order when it writes a selection.
- `GET /api/v1/platform/bots/<uuid>/plugin-registrations[?route_id=&include_disabled=1]` / MCP `list_bot_plugin_registrations` return each plugin's commands, events and `event_processors` (hook → `messaging` / `agent` / `command`).

## SDK and compatibility

- The SDK dispatches events in the order of the plugin list the host passes and skips plugins without a handler for the event; the runtime reports per-plugin event/command registrations.
- Core still pins the published `langbot-plugin`. On a runtime without the registrations action, the API returns `plugins: null` and the WebUI shows hooks as unknown; dispatch falls back to the old behavior. New plugin→host fields follow the host opt-in rule.

## Migrations

| Revision | Change | Downgrade |
| --- | --- | --- |
| `0057_bot_command_settings` | bot `command_settings` | drops column |
| `0058_platform_command_sync` | platform command menu sync state | drops columns |
| `0059_bot_message_policy` | moves trigger/safety/general output to `bots.message_policy`; existing bots get the neutral policy and each route pointing at a pipeline gets that pipeline's former settings as its override; moved keys backed up verbatim in `legacy_pipelines.message_policy_backup` | restores the backup into pipeline configs |
| `0060_bot_plugin_selection` | bot plugin selection = union of the routed pipelines' selections (any enable-all ⇒ enable-all); routes whose pipelines differed get route overrides; command-bound plugins join the selection | removes the selection |

New bots use the defaults a new pipeline had before (`default_policy()`), with all plugins enabled.

## Known limitations

- `PromptPreProcessing` does not fire for Agents.
- `NormalMessageResponded` cannot rewrite streamed replies.
- Native streaming on Discord and Lark cannot render the @sender / quote of the first frame (`adapters/00-index.md`).
- The debug chat cannot preview long text, @sender and other outbound effects.
- The Cloud daily message quota is still enforced in the Chat stage chain only (unchanged from master).

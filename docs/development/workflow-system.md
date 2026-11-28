# Workflow processors

A bot route with `target_type: workflow` sends a message to a workspace-owned tree. The graph has one `start`, one parent per subsequent step, and at most one child per branch. A terminal step needs no outgoing edge. Stable node IDs are template names; display names can change without breaking references.

## Execution

The catalog at `GET /api/v1/workflows/_/node-types` describes each step’s configuration, outputs and branches. The executor follows one path and records rendered inputs, outputs, branch, timings and errors per step. Jinja expressions can reference ancestor outputs, scoped memory and time. The workflow timezone defaults to UTC. Memory scopes are `run`, `user`, `group` and `workflow`.

Message routing admits the entry query once. A handoff to Chat, Agent or another workflow reuses that admission; replacement text must pass inbound content filtering. Target replies use their normal outbound hooks and policy. Nested handoffs are bounded at eight levels. Explicit sends target the selected conversation rather than replying to the originating message.

## Triggers

`workflow.triggers` holds one or more triggers (`workflow/triggers.py` validates them):

- `message` and `event`: a bot route points `message.received` or platform events at the workflow. An event trigger lists concrete events or patterns (`group.*`, `*`), never `message.received`; `accepts_event` matches the delivered event and `accepts_route` checks that a (possibly wildcard) route overlaps the triggers when the bot is saved. `GET /api/v1/workflows` returns each workflow's `event_patterns` so the route picker offers only compatible workflows. The typed event is `start.event` (with `start.event_type`); friend and feedback events, which have no chat, reply to the person.
- `command`: `RuntimeBot._try_handle_workflow_command` runs after system and plugin commands fail to match, so they win name clashes. It reuses the bot command prefix, `admin_only` uses the bot's admin list, and admission goes through the message policy of the route the message would otherwise match. Arguments are split by spaces with the last one taking the rest (`parse_command_args`) and exposed as `start.args`. `/help` lists workflow commands the sender may run.
- `schedule`: `WorkflowScheduler` wakes every minute and only considers workflows whose schedule names a bot that this process runs. A Workspace's bots run in exactly one process, so a schedule fires once per minute slot without an extra lock. Cron (five fields) or `every` minutes are evaluated in the workflow timezone. Each target gets its own run; `reply` sends to that target. Missed slots while the process is down are not replayed.
- `webhook`: `POST /api/v1/workflows/hooks/<bot_uuid>/<workflow_uuid>/<secret>` (no auth, JSON object ≤256 KiB). The bot must be running in this process; the secret is generated on save and compared in constant time. The body is `start.payload`.

Schedules and webhooks run through `RuntimeBot.run_triggered_workflow` inside `_run_event_delivery`, which opens the tenant scope required on Cloud.

## Platform and event actions

The `platform` step shares the Agent platform tool catalog (`agent/runner/platform_tools.py`, returned as `platform_tools` by the node-types endpoint) and runs it through `execute_platform_tool`. Each run carries a session shaped like an Agent run: bot routes freeze the event targets with `RuntimeBot._workflow_platform_context`; schedules and webhooks carry only their target, so event-scoped tools (`event_*`) fail there. Event tools bind the triggering message, member, group or request (`event_respond_friend_request` uses the real `request_id`); platform tools take explicit IDs and may run on another bot. Messages leave only through `reply`/`send`, so `event_reply`, `platform_send_message` and `request_interaction` are rejected. Standard APIs outside the catalog (`edit_message`, `forward_message`, request handling by ID, `upload_file`, `get_file_url`) and adapter `call_platform_api` actions call the adapter directly after checking `get_supported_apis()`.

## Media

`tts` stores synthesized audio in the media cache and returns a `/api/v1/files/media/<file>` reference. `asr` reads such a reference. `reply`/`send` embed cached media as base64 because adapters cannot fetch relative LangBot URLs; other image or voice URLs must pass the outbound SSRF check.

## Editing and testing

Create or update a graph through `/api/v1/workflows`. The detail and update responses include `workflow` and `issues`; invalid definitions may be edited but cannot execute. `POST /<uuid>/test` takes `text`, `session_type` and optionally an unsaved `graph` and `triggers`, or an `event` (`{type, data}`) to simulate a platform event. Test runs use a WebUI debug session like Agent debugging, so every platform and event action is mocked and never reaches a bot. A text starting with `/` that names one of the workflow's commands is parsed into `start.args`. A saved test requires `runtime.operate`; a draft additionally requires `resource.manage`. Tests capture replies rather than replying to a platform user. The response includes the execution UUID, status, error, handoff, replies and ordered steps. Inspect recorded runs with `GET /<uuid>/executions` and `GET /<uuid>/executions/<execution_uuid>`.

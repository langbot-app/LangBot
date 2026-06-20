---
name: langbot-eba-adapter-dev
description: Build, refactor, and test LangBot platform adapters for the Event-Based Agents architecture. Use when adding or migrating Telegram, Discord, or other messaging platform adapters to the EBA adapter layout, validating unified event/message conversion, writing live adapter probes, or using standalone plugin runtime plus Computer Use for end-to-end platform testing.
---

# LangBot EBA Adapter Development

Use this skill when implementing or reviewing a LangBot platform adapter under the Event-Based Agents architecture.

## Core Rule

Do not let platform-native event or message shapes leak into LangBot's common path. Each adapter must convert incoming SDK objects into unified EBA entities before dispatch:

- Events: `langbot_plugin.api.entities.builtin.platform.events`
- Message chains: `langbot_plugin.api.entities.builtin.platform.message.MessageChain`
- Users/groups/members: `langbot_plugin.api.entities.builtin.platform.entities`
- Raw platform objects may remain only in `source_platform_object` for debugging or platform-specific escape hatches.

## Start Here

1. Read the EBA design docs in `LangBot/docs/event-based-agents/`.
2. Read the architecture-level acceptance checklist before writing or validating code:
   - `LangBot/docs/event-based-agents/adapters/acceptance-checklist.md`
3. Read the current reference adapter before writing code. Prefer Telegram first:
   - `LangBot/src/langbot/pkg/platform/adapters/telegram/`
   - `LangBot/docs/event-based-agents/adapters/telegram.md`
4. Read the legacy source adapter for the target platform:
   - `LangBot/src/langbot/pkg/platform/sources/<platform>.py`
   - `LangBot/src/langbot/pkg/platform/sources/<platform>.yaml`
5. Inspect SDK entity definitions in `langbot-plugin-sdk/src/langbot_plugin/api/entities/builtin/platform/`.
6. Search before assuming APIs. Platform SDKs change often.

## Adapter Layout

Create one directory per adapter:

```text
LangBot/src/langbot/pkg/platform/adapters/<platform>/
├── __init__.py
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
├── types.py
└── <platform>.svg
```

Add optional helpers such as `voice.py` only when the platform has a real domain-specific surface.

Ensure `pyproject.toml` package data includes adapter assets:

```toml
package-data = { "langbot" = ["templates/**", "pkg/platform/sources/*", "pkg/platform/adapters/**", ...] }
```

## Implementation Checklist

- `manifest.yaml` declares `metadata.name`, config schema, supported events, common APIs, and platform-specific APIs.
- `adapter.py` creates the platform client, subscribes to native events, filters self/bot loops where appropriate, calls `event_converter.target2yiri(...)`, then dispatches the EBA event.
- `event_converter.py` maps native events to EBA event classes such as `MessageReceivedEvent`, `MessageEditedEvent`, `MessageDeletedEvent`, `MessageReactionEvent`, `MemberJoinedEvent`, `BotInvitedToGroupEvent`, and `PlatformSpecificEvent`.
- `message_converter.py` maps native messages to `MessageChain`, and maps `MessageChain` back to the platform send format.
- `api_impl.py` implements common EBA APIs: send, reply, edit, delete, forward, user/group/member lookup, moderation, upload/file URL, leave group.
- `platform_api.py` keeps platform-specific calls behind `call_platform_api(action, params)`.
- Unsupported common APIs must raise explicit SDK platform errors such as `NotSupportedError`; do not silently no-op.
- Destructive APIs such as kick, ban, leave, delete, or moderation must be gated in live tests and documented.

## Conversion Contract

For message events, the common shape should look like this regardless of platform:

```python
platform_events.MessageReceivedEvent(
    type="message.received",
    adapter_name="<platform>",
    message_id=<platform_message_id>,
    message_chain=platform_message.MessageChain([...]),
    sender=platform_entities.User(...),
    chat_type=platform_entities.ChatType.PRIVATE or ChatType.GROUP,
    chat_id=<conversation_or_channel_id>,
    group=platform_entities.UserGroup(...) or None,
    source_platform_object=<raw_object>,
)
```

Message content should use common components:

- `Source` for original message id/time when available.
- `Plain` for text.
- `At` / `AtAll` for mentions.
- `Image`, `Voice`, `File` for media.
- `Forward` only when the platform can represent or emulate it safely.

If a platform event cannot cleanly map to a common event, emit `PlatformSpecificEvent` with a compact `action` and structured `data`.

## Unit Tests

Add focused tests under `LangBot/tests/unit_tests/platform/test_<platform>_eba_adapter.py`.

Cover at least:

- Manifest supported events match adapter `supported_events()`.
- Manifest supported APIs match adapter `supported_apis()`.
- Platform API map matches manifest actions.
- Dispatcher chooses the most specific EBA listener.
- Message converter maps every supported common component both directions where possible:
  - `Source`
  - `Plain`
  - `At`
  - `AtAll`
  - `Image`
  - `Voice`
  - `File`
  - `Quote`
  - `Face`
  - `Forward`
  - `Unknown`
  - mixed chains preserving order
- Event converter maps message received/edited/deleted/reaction, raw uncached gateway events, member events, and bot join/leave events.
- Send/reply methods pass correct platform kwargs and return `MessageResult`.

Run the existing reference adapter tests too:

```bash
cd LangBot
uv run pytest tests/unit_tests/platform/test_<platform>_eba_adapter.py tests/unit_tests/platform/test_telegram_eba_adapter.py
uv run python -m py_compile tests/e2e/live_<platform>_eba_probe.py
git diff --check
```

## Live Test Workflow

Direct adapter live probes are useful diagnostics, but they are not sufficient acceptance evidence for EBA. Treat `tests/e2e/live_<platform>_eba_probe.py` as an auxiliary tool only. The final adapter record must distinguish:

- `plugin-e2e-ui`: real SDK plugin through standalone runtime, LangBot core, adapter, and a real/simulator UI action. This can mark an inbound UI item complete.
- `plugin-e2e-protocol`: real SDK plugin through standalone runtime, LangBot core, adapter, and a protocol-boundary injected event. This is useful evidence but must not be claimed as UI coverage.
- `plugin-e2e-outbound`: real SDK plugin calls an API and the bot output is visible in the real/simulator UI. This can mark send/API coverage complete.
- `adapter-live`: direct adapter probe connected to a real/simulator endpoint. This is auxiliary only.
- `unit`: mocked conversion/API-shape coverage. This is auxiliary only.
- `not-supported`: platform protocol or SDK has no equivalent. Must include the reason.
- `blocked`: intended capability could not be verified. This is not complete.

Write a live probe in `LangBot/tests/e2e/live_<platform>_eba_probe.py`. It should:

1. Read token/client ids from environment variables or CLI args.
2. Start the adapter directly.
3. Register an EBA listener and write JSONL evidence to `LangBot/data/temp/`.
4. Wait for a real user/platform event instead of fabricating the entrypoint.
5. Exercise common APIs and `call_platform_api` actions.
6. Observe returned gateway events for edit/delete/reaction/member/bot lifecycle where available.
7. Print a summary containing passed, failed, skipped, and observed event types.
8. Redact or avoid printing secrets.
9. Keep destructive operations behind flags and run them last.

Use Computer Use when the user asks for real platform end-to-end coverage. Actually send messages/click reactions in the platform UI or otherwise trigger real user-side events; do not replace that with unit tests.

For media/component acceptance, keep the direction and trigger source explicit:

- Real inbound media only counts when a human-side platform UI or simulator UI sends the image/file/voice to the bot and the plugin JSONL records the corresponding common component.
- Bot outbound media only proves `send_message`/adapter send conversion. It does not prove inbound conversion.
- Protocol-boundary injection, such as sending a OneBot event directly into a reverse WebSocket adapter, is useful and should be labelled `plugin-e2e-protocol`, but it must not be reported as UI-level end-to-end media upload.
- If the UI cannot send or upload the media, record the item as `blocked` with the exact client/simulator limitation.

## Standalone Runtime + Plugin Test

When validating the whole LangBot EBA path, test with the SDK standalone runtime and a real test plugin. This is the required acceptance path; direct adapter calls do not prove the EBA architecture path.

The required path is:

```text
Real platform / simulator UI
  -> platform SDK native event
  -> adapter event converter
  -> unified EBA event/entity/message types
  -> LangBot core event dispatch
  -> standalone SDK runtime
  -> real test plugin listener
  -> plugin calls platform APIs through SDK
  -> LangBot core API dispatch
  -> adapter API implementation
  -> real platform / simulator UI
```

Typical shape:

```bash
# Terminal 1, SDK repo
cd langbot-plugin-sdk
uv run python -m langbot_plugin.cli.__init__ rt \
  --debug-only \
  --ws-control-port 5400 \
  --ws-debug-port 5401 \
  --skip-deps-check

# Terminal 2, LangBot repo
cd LangBot
export PYTHONPATH=/absolute/path/to/langbot-plugin-sdk/src:${PYTHONPATH:-}
uv run main.py --standalone-runtime

# Terminal 3, plugin directory
export DEBUG_RUNTIME_WS_URL=ws://127.0.0.1:5401/plugin/ws
export EBA_PROBE_LOG=/absolute/path/to/LangBot/data/temp/<platform>_eba_plugin_probe.jsonl
export EBA_PROBE_API=1
export EBA_PROBE_COMPONENT_SWEEP=1
export EBA_PROBE_PLATFORM_API=1
uv --project /absolute/path/to/langbot-plugin-sdk run python -m langbot_plugin.cli.__init__ run
```

Use an EBA probe plugin that subscribes to all relevant EBA event classes and runs SDK API calls after the first `MessageReceived`.

The plugin evidence should be JSONL and include:

- event class and `event.type`
- adapter name
- chat type and chat ID
- sender/user/group IDs with secrets redacted
- `bot_uuid` and `adapter_name`, proving LangBot filled common routing fields before plugin dispatch
- received `message_chain` component list
- API action name, input summary, result or error
- unsupported or blocked reason when an item is skipped

For full adapter acceptance, enable both probe sweeps:

- `EBA_PROBE_COMPONENT_SWEEP=1` sends the required outbound message components through `send_message`.
- `EBA_PROBE_PLATFORM_API=1` calls common safe APIs plus selected `call_platform_api` actions for the adapter.

The SDK must support `plugin.call_platform_api(bot_uuid, action, params)` for platform-specific acceptance. If the SDK cannot call a platform-specific action from the plugin, the adapter cannot be fully accepted even if direct adapter probes pass.

## Required EBA Acceptance Coverage

Before marking an adapter migrated, fill out an adapter record against `LangBot/docs/event-based-agents/adapters/acceptance-checklist.md`.

At minimum, the record must cover these categories:

- Message receive component tests through `plugin-e2e-ui`: `Source`, `Plain`, `At`, `AtAll`, `Image`, `Voice`, `File`, `Quote`, `Face`, `Forward`, `Unknown`, and mixed chains where the platform supports them. Protocol-only receive evidence must be labelled `plugin-e2e-protocol`.
- Message send component tests through `plugin-e2e-outbound`: `Plain`, `At`, `AtAll`, `Image`, `Voice`, `File`, `Quote`, `Face`, `Forward`, and mixed chains where the platform supports them.
- Every event declared in `manifest.yaml -> spec.supported_events`.
- Every common API declared in `manifest.yaml -> spec.supported_apis.required` and `optional`.
- Every action declared in `manifest.yaml -> spec.platform_specific_apis`.
- Compatibility tests for manifest declarations, legacy message listener fallback, EBA listener specificity, bot self-message filtering, and `source_platform_object` reply/debug behavior.

Do not declare an event or API in the manifest unless it has an implementation path and an acceptance entry. If a platform or simulator lacks a capability, document it as `not-supported` or `blocked` rather than silently omitting the test.

## Common Pitfalls

- `get_bots()` may return bot dictionaries, not UUID strings. Probe plugins should select an enabled dict and pass `bot["uuid"]` to `get_bot_info()` and `send_message()`.
- Make sure the probe subscribes to every event you claim to verify. Missing `MessageDeleted` subscription can make a working adapter look untested.
- Some platforms emit both cached and raw gateway events, producing duplicate evidence for delete/reaction. Count this explicitly; do not treat duplicates as failure unless semantics differ.
- Self-message filtering is platform-specific. Filter bot-originated `message.received` loops, but do not accidentally filter edit/delete events needed for bot-owned API probes.
- Reaction events may be filtered for bot self reactions. To test user reaction add/remove, use real UI interaction or a real user token path if permitted.
- File uploads usually happen as message attachments. A standalone `upload_file` API may need to be `NotSupportedError`.
- Live probes should not leak bot tokens through command output, logs, docs, or final answers.
- Discord requires privileged intents for message content and members. Missing intents can look like converter bugs.
- Telegram Bot API exposes only limited member lists; document capability gaps.
- Do not mark moderation APIs verified unless they ran against a disposable target member/bot.
- If `leave_group` is tested, run it last because the test bot will be removed from the server/group.
- Restore local LangBot DB/test state after live runs if you enabled temporary bots or changed plugin settings.

## Documentation Record

Add or update `LangBot/docs/event-based-agents/adapters/<platform>.md` in the same style as Telegram:

- Status and adapter directory.
- Configuration table matching manifest fields.
- Supported EBA event list.
- Common API table with support and limitations.
- `call_platform_api` action list.
- Receive component table with evidence level per component.
- Send component table with evidence level per component.
- Event table with evidence level per event.
- Common API table with evidence level per API.
- Platform-specific API table with evidence level per action.
- Live test record with exact date, endpoint/simulator, standalone runtime command, test plugin path/name, JSONL evidence path, channel/group type, observed events, APIs exercised, destructive operations, and skipped items.

Be honest. Put untested or skipped APIs in the document with the reason. Do not imply full parity when a platform cannot provide the same information density.

## Before Finishing

- Run unit tests and compile the live probe.
- Run the standalone runtime plugin E2E path for every required acceptance item that the platform supports.
- Run `git diff --check`.
- Summarize live JSONL evidence by event type.
- Stop all long-running runtimes and probes.
- Confirm no secrets are staged.
- Leave unrelated untracked files alone.

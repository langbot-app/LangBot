# Telegram 4.11 adapter acceptance

Validated on 2026-10-11 using the Telegram Web client and LangBot WebUI through computer use. Bot registration, bot configuration, processor bindings, group membership changes, and test messages were performed through the UI. No direct Bot API calls or database mutations were used to simulate acceptance traffic.

## Environment

- Core 4.11.0rc2, SDK 0.7.11rc2 on their main branches.
- OSS development mode, standalone Plugin Runtime and standalone Docker-backed Box Runtime.
- Dedicated new Telegram bot and dedicated test group; no unrelated conversations used.
- Pipeline and Agent: LocalAgent with gemini-3-flash-preview. Plugin processors: RunnerDemo community and observer.

## Real message coverage

| Path | Verification |
| --- | --- |
| Pipeline private text | TG-P01 received an actual reply. |
| Pipeline group text and streaming | TG-G04 and TG-STREAM05; observed partial output growing from 12 to 22 to 60 lines, ending with STREAM-END. |
| Pipeline private streaming | TG-PRIVATE-STREAM10; observed 8 partial lines progressing to 80 complete lines and STREAM-DONE. |
| Pipeline incoming image | TG-IMG01 correctly identified the red left half and blue right half of a synthetic image. |
| Pipeline incoming file | TG-FILE01 read marker TG-FILE-7319 and calculated 17 + 25 + 38 = 80. |
| Pipeline outgoing media | TG-FILE07 delivered a real green PNG and verified.txt as Telegram attachments. |
| Invalid image fallback | TG-FALLBACK08 delivered a-check.txt once and an intentionally invalid nine-byte PNG as a document once, without replaying the preceding file. |
| Agent private and group | TG-A01/A02/A03 and TG-COEXIST01 exercised event_reply and real delivery. Historical conversation wording influenced early replies; explicit current instructions were used for subsequent media tests. |
| Agent group image input | TG-AGENT-GIMG02 correctly identified left red/right blue. |
| Agent group file input/output | TG-AGENT-GFILE01 read the marker and sum and delivered result.txt (27 bytes); run completed in 10.72 seconds. Downloaded the Telegram attachment and verified its contents: Code: TG-FILE-7319 and Sum: 80. |
| Agent group image output | TG-AGENT-GOUT01 generated a real 64x64 PNG using Box, delivered it as a photo, and completed in 12.96 seconds. |
| Plugin private/group text | TG-PLUGIN-P02 and TG-REACTION-02 echo replies were delivered with completed runs after fixing MessageResult. |
| Plugin attachment events | Community processor independently recorded Image and File components, with completed runs. It intentionally sends no reply without its command prefix. |
| Independent subscriptions | TG-COEXIST01 produced both the plugin reply and Agent reply. |

Agent event_reply is a complete send, not token streaming. RunnerDemo community provides progress logs but no streaming or generated-media command; those outputs were tested through Pipeline and Agent instead. This is not a claim that every processor implements every output mode.

## Real event coverage

| Event | UI action and observed result |
| --- | --- |
| message.received | Sent private/group text and attachments. |
| message.edited | Edited TG-EDIT01; Agent reported the actual edited event. |
| message.reaction | Added then removed thumbs-up; observer payloads retained the emoji with is_add true/false. |
| group.member_joined | Added a dedicated existing test bot; observer recorded the event and community sent a welcome. |
| group.member_left | Removed that test bot; event had is_kicked true and community sent a departure notice. |
| group.member_banned | Restricted that test bot's sending permission; observer recorded the restriction event. |
| bot.invited_to_group | Re-added the QA bot; observer completed at 10:04:12. |
| bot.removed_from_group | Removed the QA bot while restricted; observer completed at 10:03:55. |
| bot.muted | Disabled sending permission; indefinite duration was null after the fix. |
| bot.unmuted | Restored sending while another restriction remained; observer completed at 10:02:29. |
| platform.specific | Changed administrator status; observer recorded my_chat_member_updated. |

This covers each declared event type, not every possible Telegram platform-specific subtype. Administrator-only updates were tested with a minimal administrator role in the dedicated group. Replying while muted/removed was not treated as an expected successful action.

## Fixes driven by acceptance

1. Normalize numeric conversation IDs before building the Agent protocol context.
2. Return MessageResult from Telegram send/reply so successful delivery does not subsequently fail plugin action decoding.
3. Deliver terminal stream attachments and remove an empty Thinking placeholder for attachment-only completions.
4. Fall back to document delivery for known Telegram photo encoding/dimension rejections, preserving earlier deliveries.
5. Register MessageReactionHandler with the correct keyword argument instead of accidentally filtering by chat ID.
6. Preserve the removed emoji and distinguish additions from removals.
7. Interpret Telegram's Unix-epoch restriction expiry as indefinite; calculate finite duration from event time.
8. Recognize partial unmute and removal from a restricted state.

## Automated and documentation validation

- 134 focused tests passed across Telegram legacy/new adapters, native stream completion, Omni parity, and Agent event-first protocol.
- Ruff and git diff whitespace checks passed.
- Chinese, English, and Japanese Telegram guides updated with processor selection, privacy mode, permissions, streaming/media boundaries, event semantics, and troubleshooting.
- Sanitized real group screenshot included in all three guides; rendered image verified in the local built documentation.
- Documentation tests and production static build passed (38 Node tests; 19 Python tests with one skip; 31 static-build tests).

After synchronizing the documentation main branch, a stale DingTalk screenshot assertion in the migration test was updated to match the current guide; the full documentation suite passed again.

Provider-specific errors observed with an earlier model were separated from adapter failures; successful acceptance uses the model stated above. This validation does not assert compatibility with every model provider, Telegram update subtype, or plugin implementation.

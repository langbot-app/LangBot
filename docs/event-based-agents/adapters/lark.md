# Lark / Feishu EBA Adapter Migration Record

Status: migrated with unit coverage and partial live plugin E2E. WebSocket text reached the standalone runtime once in the LangBot organization test app, but the latest real UI image/file inbound attempts did not reach the local adapter log, so media receive is not release-complete yet.

Adapter directory: `src/langbot/pkg/platform/adapters/lark/`

## What Changed

The Lark/Feishu adapter now has an Event-Based Agents adapter package with:

- `manifest.yaml` for adapter metadata, configuration, events, common APIs, platform-specific APIs, app type, and communication mode.
- `adapter.py` for self-built/store app token handling, WebSocket long connection startup, Webhook callback handling, card feedback, streaming-card replies, and EBA dispatch.
- `event_converter.py` for native Feishu events to common EBA events.
- `message_converter.py` for Feishu text/post/image/file/audio payloads to/from common `MessageChain` components.
- `api_impl.py` for common EBA API implementations.
- `platform_api.py` for Feishu-specific `call_platform_api` actions.

The legacy `lark` adapter remains available while the EBA adapter is registered separately as `lark-eba`.

## Configuration

| Field | Required | Notes |
|-------|----------|-------|
| `app_id` | yes | Feishu/Lark application App ID. |
| `app_secret` | yes | Feishu/Lark application App Secret. |
| `bot_name` | yes | Must match the bot name so group mentions can be recognized. |
| `enable-webhook` | yes | `false` uses WebSocket long connection; `true` uses Request URL/Webhook callbacks. |
| `webhook_url` | no | Generated callback URL for Webhook mode. |
| `encrypt-key` | no | Webhook decrypt key when event encryption is enabled. |
| `enable-stream-reply` | yes | Enables streaming replies through an updating Feishu card. |
| `app_type` | no | `self` for self-built apps; `isv` for store apps. |
| `bot_added_welcome` | no | Optional group welcome message sent after bot-added events. |

## Application And Communication Modes

| Mode | Support | Implementation |
|------|---------|----------------|
| Self-built application | implemented | Uses standard app credentials and tenant token behavior from the Feishu SDK client. |
| Store application | implemented | Builds an ISV client, requests app tickets, and resolves app/tenant access tokens with per-tenant caching. |
| WebSocket long connection | implemented | Registers `im.message.receive_v1` and card-action callbacks through `lark_oapi.ws.Client`. |
| Webhook Request URL | implemented | Handles URL verification, encrypted payloads, message events, app-ticket events, bot-added events, and card-action feedback. |

## Supported Events

| Event | Support | Evidence |
|-------|---------|----------|
| `message.received` | implemented | Unit coverage for private and group native events to common EBA events. |
| `bot.invited_to_group` | implemented | Webhook bot-added event maps to common bot invite event and optional welcome send. |
| `platform.specific` | implemented | Unknown callback events are preserved as `platform.specific`. |
| `FeedbackEvent` | compatibility event | Card button feedback is still dispatched through the existing SDK `FeedbackEvent` type. |

## Receive Components

| Component | Support | Evidence |
|-----------|---------|----------|
| `Source` | supported | Unit coverage; live private text evidence. |
| `Plain` | supported | Text and post payloads convert to common text; live private text evidence. |
| `At` | supported | Feishu mentions map to common `At` with user ID and display name. |
| `AtAll` | supported | `user_id=all` maps to common `AtAll`. |
| `Image` | supported | Image payloads download through message resource API and map to common `Image`; real UI image send attempted, but not observed in local plugin evidence yet. |
| `Voice` | supported | Audio payloads download through message resource API and map to common `Voice`. |
| `File` | supported | File payloads download through message resource API and map to common `File`; real UI file send attempted, but not observed in local plugin evidence yet. |
| `Quote` | supported | Parent/thread reply lookup maps quoted content into common `Quote`. |
| `Face` | not native common mapping | Feishu emoji/stickers are not exposed as a portable common `Face` component here. |
| `Forward` | not-supported inbound | Feishu does not expose a portable structured forward event in this adapter. |

## Send Components

| Component | Support | Evidence |
|-----------|---------|----------|
| `Plain` | supported | Unit coverage; sends Feishu `text`. |
| `At` | supported | Unit coverage; sends Feishu `post` at element. |
| `AtAll` | supported | Unit coverage; sends Feishu `post` at-all element. |
| `Image` | supported | Uploads image resource and sends Feishu `image`. |
| `Voice` | supported | Uploads OPUS/audio resource and sends Feishu `audio`. |
| `File` | supported | Uploads file resource and sends Feishu `file`. |
| `Quote` | supported/fallback | Sends quote marker plus origin content. |
| `Face` | not-supported | No portable send mapping. |
| `Forward` | flattened fallback | Flattens forward nodes into text/media messages. |

## Common APIs

| API | Support | Notes |
|-----|---------|-------|
| `send_message` | supported | Supports private/open_id and group/chat_id targets; live plugin outbound component sweep produced visible Feishu messages. |
| `reply_message` | supported | Replies to the source Feishu message; fixed to recover the native Feishu message ID from legacy-wrapped source events. |
| `get_message` | cache-backed/API-backed | Returns cached inbound event where possible and converts uncached Feishu message API items into common `MessageReceivedEvent`. |
| `get_group_info` | supported | Uses cached group or Feishu chat metadata. |
| `get_group_member_info` | limited | Uses cached user data when available. |
| `get_user_info` | limited | Uses cached user data when available. |
| `get_file_url` | limited | Returns `file://` paths from downloaded inbound resources; remote Feishu resource download uses platform-specific API params. |
| `call_platform_api` | supported | See below. |

## Platform-Specific APIs

| Action | Support | Evidence |
|--------|---------|----------|
| `check_tenant_access_token` | supported | Unit coverage. |
| `refresh_app_access_token` | supported | Store-app token path implemented. |
| `refresh_tenant_access_token` | supported | Store-app tenant token path implemented. |
| `get_chat` | supported | Feishu chat metadata API wrapper. |
| `get_message` | supported | Feishu message API wrapper with JSON-safe return values for plugin calls. |
| `get_message_resource` | supported | Feishu message resource download wrapper. |

## End-to-End Evidence

Current code-level evidence:

- `tests/unit_tests/platform/test_lark_eba_adapter.py`
- `PYTHONPATH=../langbot-plugin-sdk/src uv run pytest tests/unit_tests/platform/test_lark_eba_adapter.py -q`

Live evidence collected on May 11, 2026:

- Standalone runtime: `uv run lbp rt --ws-control-port 5400 --ws-debug-port 5401 --skip-deps-check`
- LangBot: `uv run main.py --standalone-runtime --debug`
- Plugin: `LangBot__EBAEventProbe`
- Feishu org/app: LangBot organization, `LangBotDev` private chat.
- Observed plugin JSONL: one private `MessageReceived` event with `Source + Plain`; plugin API probe then exercised bot discovery, bot info, `send_message`, outbound component sweep, storage/list APIs, and safe platform API calls.
- Real UI sends attempted after the fixes: private text, local file, and image/video image upload. These appeared in the Feishu client but did not append new `EBAEventProbe` records in the local JSONL during this run.
- Fixes from live testing: reply path now extracts the native Feishu `message_id` from legacy-wrapped source events; WebSocket callbacks are scheduled onto the adapter event loop instead of assuming the SDK callback has a running asyncio loop; platform API results are converted to JSON-safe values.

Live E2E items still required before marking release-complete:

- WebSocket self-built app in LangBot organization: repeat private text after callback-loop fix, plus private image/file/audio and group mention message received by `EBAEventProbe`.
- Webhook self-built app in LangBot organization: URL verification plus text/image/file message received by `EBAEventProbe`.
- Store app token path: at least token acquisition/tenant-token safe API through `call_platform_api`; full message E2E if a LangBot organization store-app fixture is available.
- Outbound component sweep: text, mention, at-all, image, file, voice where Feishu accepts the fixture, quote/fallback, and forward/fallback.
- Safe platform API sweep: token check, chat metadata, message lookup, and message resource download using real inbound IDs.

## Known Limits

- Store-app live E2E requires a real ISV app ticket/tenant installation fixture.
- Current LangBot organization WebSocket run connected successfully but did not deliver the latest UI-sent image/file attempts to local plugin evidence; this blocks release-complete media acceptance.
- Feishu native emoji/sticker semantics are not represented as common `Face`.
- Destructive org or chat mutations are not declared in this adapter.

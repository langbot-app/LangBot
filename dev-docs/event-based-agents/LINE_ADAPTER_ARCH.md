# Native EBA LINE Adapter — Design

<!-- Placed under LangBot docs/event-based-agents/ as the LINE-adapter–specific design doc. -->

## 1. Positioning

Native EBA LINE Adapter is LangBot's **native Event-Based Agent online-platform adapter**,
making LINE one of LangBot's native `source`s, wired directly into EBA's `MessageChain`
abstraction and platform-event dispatch.

Core principle: **the framework is invisible to the platform; the platform is pluggable to the framework**
— business logic ports across Telegram / Slack / LINE.

## 2. Directory structure

```
pkg/platform/adapters/line/
├── __init__.py                     # package init / plugin manifest
├── line_types.py                   # event / payload type contracts
├── platform_api.py                 # platform capability interface contract
├── adapter.py                      # LineAdapter (AbstractPlatformAdapter base)
│   ├── get_supported_events() / get_supported_apis()   # capability declaration
│   ├── send_message()              # push_message push
│   └── message handling
├── api_impl.py                     # SDK access abstraction (retry wrapper / decoupling)
├── event_converter.py              # LINE event → EBA payload (_sdk_to_payload staticmethod)
│   └── _platform_specific()        # event dispatch to platform.<namespace>
├── message_converter.py            # EBA MessageChain ↔ LINE payload bidirectional
├── send_api.py                     # LineSendApi (reply/push/flex + RetryPolicy) + Flex cards
├── streaming.py                    # LineStreamClient (WebSocket skeleton) + LineStreamOutput
└── test_*.py                       # domain boxed self-tests
```

## 3. Inbound flow (LINE → EBA)

```
LINE SDK event
  ├─ MessageReceivedEvent ─▶ _sdk_to_payload() ─▶ PlatformPayload(sender, chat_type, chat_id, source, …)
  │     _platform_specific(type="message.received") ─▶ platform.message.received
  │
  ├─ FollowEvent   ─▶ _platform_specific("user.followed")
  │  UnfollowEvent ─▶ _platform_specific("user.unfollowed")
  │  JoinEvent     ─▶ _platform_specific("group.joined")
  │  LeaveEvent    ─▶ _platform_specific("group.left")
  │  PostbackEvent ─▶ _platform_specific("platform.specific.postback")
  │  BeaconEvent   ─▶ _platform_specific("platform.specific.beacon")
  │
  ├─ ImageMessage ─▶ _platform_specific("image.received") ─▶ adapter.download_message_content()
  │  Audio / Video ─▶ download_message_content()
  │
  └─ Message.edited / Feedback / group.*  ─▶ 未實測則未宣告
```

## 4. Outbound flow (EBA → LINE)

```
EBA MessageChain (Plain/At/Image/… / platform.Component)
  └─ yiri2target() ─▶ LINE payload dict
        ├─ text       → {"type":"text","text":...}
        ├─ image      → {"type":"image","original_content_url":...,"preview_image_url":...}
        ├─ flex 卡片  → {"type":"flex","alternative_text":...,"flex":{…bubble/carousel…}}
        └─ PlatformComponent(line) → flex payload (via send_flex)
  └─ LineSendApi
        ├─ reply_message()   ← passive reply shortcut (ReplyToken; expiry falls back to push)
        └─ push_message()    ← active push
```

**Flex Message card family** (`send_api.py`, pure builders, zero SDK dependency):
`FlexText / FlexBox / FlexButton / FlexBubble / FlexCarousel / FlexImage / FlexCard`
plus `flex_message_object / list / from_bubbles / flex_container / send_flex`.

## 5. Capability-declaration boundary

```python
get_supported_events()   # verified events only
get_supported_apis()     # verified APIs only
```

| Capability | Status | Boundary basis |
|------|------|------|
| message.received / send / reply | ✅ send-receive closed loop | verified dispatch + self-tests |
| group.* / user.* event mapping | ✅ mapping framework | event_type values SDK-verified |
| image.received / download_content | ✅ framework | in-box mapping |
| flex.send | ✅ framework | in-box |
| get_group_summary / get_user_profile / … | ⚠️ needs verification | actual SDK call not yet boxed |
| streaming (WebSocket / typewriter) | ⚠️ needs verification | SDK streaming not yet boxed |
| message.edited / feedback / beacon | not declared | not verified — not declared |

## 6. Configuration example (illustrative)

Credentials load via the SDK (not committed, no hard-coding):

```yaml
# .env (framework sketch; exact fields per SDK)
LINE_CHANNEL_ACCESS_TOKEN=<...>   # LineBotApi client credential
LINE_CHANNEL_SECRET=<...>         # webhook attachment / validation provider
```

Adoption via EBA `AbstractPlatformAdapter` contract + manifest declaration:

```python
from pkg.platform.adapters.line.adapter import LineAdapter
# LineAdapter(config=...) injects the SDK client (channel_access_token / channel_secret)
# inbound: LINE event → event_converter._sdk_to_payload → platform.<namespace>
# outbound: MessageChain → message_converter.yiri2target → LineSendApi push/reply/flex
```

## 7. Discipline

- **Zero hard-coding**: env/secret via `os.getenv`; no mutable parameters written literal.
- **No fabrication**: unverified SDK calls stay annotated as "pending verification".
- **Declare only verified capabilities**: unverified events are not declared.
- **Boxed decoupling**: self-tests carry no hard SDK dependency, so they run in CI regardless of SDK presence.

## 8. Testing & CI

```bash
cd <repo>/src/langbot
python -m pkg.platform.adapters.line.test_selftest
python -m pkg.platform.adapters.line.test_send_streaming
python -m pkg.platform.adapters.line.test_group_user_events
python -m pkg.platform.adapters.line.test_multimodal_flex
```

All-green exit 0 + Ruff/flake8 zero lint + full pytest pass → ready to open a PR.

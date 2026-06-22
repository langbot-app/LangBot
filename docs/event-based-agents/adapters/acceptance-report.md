# EBA Adapter Acceptance Report

Date: May 10, 2026

Scope:

- `telegram-eba`
- `discord-eba`
- `aiocqhttp-eba`
- `dingtalk-eba`
- `lark-eba`
- `wecom-eba`
- `wecombot-eba`
- `wecomcs-eba`
- `officialaccount-eba`
- `qqofficial-eba`
- `slack-eba`

This report follows `acceptance-checklist.md`. Evidence levels are intentionally strict:

- `plugin-e2e-ui`: real platform or simulator UI event reached LangBot, standalone runtime, and `EBAEventProbe`.
- `plugin-e2e-protocol`: real adapter endpoint event reached LangBot, standalone runtime, and `EBAEventProbe`, but the event was injected at the platform protocol boundary rather than sent through the UI.
- `plugin-e2e-outbound`: the plugin called SDK APIs and the resulting bot message was visible on the platform.
- `unit`: mocked converter/API coverage only.
- `blocked`: not completed, either because the platform/simulator/client could not trigger it or because a safe disposable fixture was unavailable.
- `not-supported`: the platform has no equivalent capability.

## Summary

| Adapter | Status | Honest acceptance summary |
|---------|--------|---------------------------|
| Telegram | Partial EBA acceptance | Real Telegram UI covered private text, group mention text, bot invite, inbound private image/file, outbound component sweep, safe SDK APIs, and safe Telegram platform APIs. Real UI inbound voice/quote was not completed in the latest plugin run. |
| Discord | Partial EBA acceptance | Real Discord UI covered group text, outbound image/file/quote/mention components, safe SDK APIs, and safe Discord platform APIs. Real UI inbound attachment/image/file/reply/mention was not completed. A later UI retry was blocked because the Discord client kept the send button disabled. |
| OneBot v11 / aiocqhttp | Partial EBA acceptance | Matcha UI covered real group text and outbound supported components/APIs. Multi-component inbound `Source/Plain/At/Face/Image/Voice/File/Quote` was verified through the real OneBot reverse WebSocket adapter endpoint, but not through Matcha UI upload/send. Matcha blocks file-send and merged-forward APIs. |
| DingTalk | Partial EBA acceptance | Real DingTalk UI covered private text, emoji-as-text inbound, private inbound image/file, outbound image/file/quote/mention fallback components, safe SDK APIs, and safe DingTalk platform APIs. Real UI inbound voice/quote and group trigger were not completed. |
| Lark / Feishu | Partial EBA acceptance | EBA adapter structure, self-built/store app config, WebSocket/Webhook mode handling, converters, common APIs, platform APIs, and unit tests are in place. One real LangBot organization WebSocket private text event reached `EBAEventProbe`; outbound component sweep was visible in Feishu. Latest real UI image/file sends did not reach local plugin evidence, so media receive remains blocked. |
| WeCom | Partial EBA acceptance | Regular WeCom application-message adapter is split into the EBA directory with manifest, converters, API mixin, platform API map, and unit tests. Private text reached `EBAEventProbe` through standalone runtime and the real WeCom client; safe plugin APIs passed. Real inbound media and broader event coverage remain pending. |
| WeComBot | Partial EBA acceptance | WeCom AI Bot is split into the EBA directory with WebSocket long connection mode and optional webhook mode, EBA message/feedback/platform-specific conversion, cache-backed common APIs, platform API map, unit tests, and a direct live probe. Private text, outbound component sweep, safe common APIs, and all declared WeComBot platform APIs reached `EBAEventProbe`; group, real inbound media, and feedback callback evidence remain pending. |
| WeCom Customer Service | Partial EBA acceptance | WeCom Customer Service is split into the EBA directory with manifest, converters, API mixin, platform API map, unit tests, docs, and a direct live probe scaffold. Real WeChat customer-side UI text reached `EBAEventProbe`; plugin outbound text/image and safe cache-backed common APIs passed. Inbound media and platform-specific API live coverage remain pending; later fallback text sends were blocked by WeCom `95001 send msg count limit`. |
| Official Account | Partial EBA acceptance | WeChat Official Account is split into the EBA directory with manifest, converters, cache-backed safe APIs, platform API map, unit tests, and a direct live probe scaffold. Real WeChat Official Account UI private text reached `EBAEventProbe`; safe cache-backed common APIs and declared platform APIs passed. Proactive outbound `send_message` is not supported because replies must be tied to inbound webhook windows; inbound image/voice live UI evidence remains pending. |
| QQ Official API | Partial EBA acceptance | QQ Official API is split into the EBA directory with manifest, converters, cache-backed safe APIs, platform API map, unit tests, docs, and a direct live probe scaffold. A real WebSocket-mode QQ Official bot reached the LangBot pipeline on `dev.rockchin.top`; reply/outbound evidence is blocked by the test model provider returning `model_not_found` for `deepseek-v3`. |
| Slack | Partial EBA acceptance | Slack is split into the EBA directory with manifest, converters, cache-backed safe APIs, platform API map, unit tests, docs, and a direct live probe scaffold. Real Slack private text reached `EBAEventProbe`; safe common APIs, outbound component fallback sweep, and declared Slack platform APIs passed. Channel mention and real inbound media evidence remain pending. |

Telegram and DingTalk now have real user-side UI image/file upload evidence in plugin JSONL. Discord and aiocqhttp do not yet have real UI inbound image/file evidence.

## Evidence Files

| Adapter | Endpoint | Evidence |
|---------|----------|----------|
| Telegram private | Telegram Lite, `@rockchinq_bot` private chat | `data/temp/telegram-plugin-e2e-rerun.jsonl` |
| Telegram private media | Telegram Lite, `@rockchinq_bot` private chat | `data/temp/telegram-plugin-e2e-media-ui.jsonl` |
| Telegram group | Telegram Lite, `Rock'sBotGroup` | `data/temp/telegram-plugin-e2e-group.jsonl` |
| Discord | Discord client, LangBot server, `#debugging` | `data/temp/discord-plugin-e2e-20260510-final.jsonl` |
| aiocqhttp UI | local Matcha, group `test group` | `data/temp/aiocqhttp-plugin-e2e-20260510-multiformat.jsonl` |
| aiocqhttp protocol | OneBot reverse WebSocket endpoint `127.0.0.1:2280/ws` | `data/temp/aiocqhttp-plugin-e2e-20260510-multiformat.jsonl` |
| DingTalk | DingTalk Mac, `LangBot Team` org private chat | `data/temp/dingtalk-plugin-e2e-20260510-rerun.jsonl` |
| DingTalk private media | DingTalk Mac, `LangBot Team` org private chat | `data/temp/dingtalk-plugin-e2e-media-ui.jsonl` |
| Lark / Feishu unit | local mocked Feishu SDK/client paths | `tests/unit_tests/platform/test_lark_eba_adapter.py` |
| Lark / Feishu partial live | Feishu Mac, LangBot organization `LangBotDev` private chat | `data/temp/lark-plugin-e2e-ws.jsonl` |
| WeCom Customer Service | WeChat customer-side UI, `客服消息 -> 浪波智能客服` on `dev.rockchin.top` | `/home/wgc/LangBotxg/LangBotEbaTest/data/temp/wecomcs_eba_plugin_probe.jsonl` |
| Official Account | WeChat desktop client, subscribed Official Account on `dev.rockchin.top` | `/home/wgc/LangBotxg/LangBotEbaTest/data/temp/officialaccount_eba_plugin_probe.jsonl` |
| QQ Official API unit | local mocked QQ Official client paths | `tests/unit_tests/platform/test_qqofficial_eba_adapter.py` |
| Slack unit | local mocked Slack client paths | `tests/unit_tests/platform/test_slack_eba_adapter.py` |
| Slack private | Slack workspace private DM on `dev.rockchin.top` | `/home/wgc/LangBotxg/LangBotEbaTest/data/temp/slack_eba_plugin_probe.jsonl` |

All plugin runs used SDK standalone runtime ports `5400/5401`, LangBot `--standalone-runtime`, and the real plugin at `langbot-plugin-demo/EBAEventProbe`.

## Unified Shape Verification

All four adapters deliver common SDK entities to plugins before LangBot core/plugin logic handles the event.

| Requirement | Telegram | Discord | aiocqhttp | DingTalk | Lark / Feishu |
|-------------|----------|---------|-----------|----------|---------------|
| `bot_uuid` filled | plugin-e2e | plugin-e2e | plugin-e2e | plugin-e2e | live plugin-e2e pending |
| `adapter_name` filled | `telegram` | `discord` | `aiocqhttp` | `dingtalk` | `lark-eba` in current unit/code; older live text evidence recorded `lark` before the naming fix |
| common `MessageChain` delivered | `Plain`, group `At + Plain`, private `Image`, private `File` | `Source + Plain` | UI `Source + Plain`; protocol `Source + Plain + At + Face + Image + Voice + File + Quote + Plain` | `Source + Plain`, private `Source + Image`, private `Source + File` | live private `Source + Plain`; unit `Source + Plain + At/Image/File`; latest live image/file blocked |
| common user/group entities | plugin-e2e | plugin-e2e | plugin-e2e | plugin-e2e private user; group not completed | live private user; unit private/group |
| raw native object isolation | raw data stays in `source_platform_object` | raw data stays in `source_platform_object` | raw data stays in `source_platform_object` | raw data stays in `source_platform_object` | raw data stays in `source_platform_object` |

## Message Receive Components

| Component | Telegram | Discord | aiocqhttp | DingTalk | Lark / Feishu |
|-----------|----------|---------|-----------|----------|---------------|
| `Source` | design gap: event has message id but chain omits `Source` | plugin-e2e-ui | plugin-e2e-ui/protocol | plugin-e2e-ui | plugin-e2e-ui private text |
| `Plain` | plugin-e2e-ui private/group | plugin-e2e-ui | plugin-e2e-ui/protocol | plugin-e2e-ui | plugin-e2e-ui private text |
| `At` | plugin-e2e-ui group mention | unit; real UI mention not completed in latest run | plugin-e2e-protocol; unit | unit; group trigger not completed | unit; group trigger not completed |
| `AtAll` | not-supported | unit only | unit only | unit/send fallback only | unit only |
| `Image` | plugin-e2e-ui private | converter/unit; real UI attachment not completed | plugin-e2e-protocol, not Matcha UI | plugin-e2e-ui private | unit; real UI image sent but not observed in plugin evidence |
| `Voice` | converter/unit; real UI inbound not completed | not-supported as native voice; audio is attachment/file | plugin-e2e-protocol, not Matcha UI | converter/unit; real UI inbound not completed | unit; real UI inbound not completed |
| `File` | plugin-e2e-ui private | converter/unit; real UI attachment not completed | plugin-e2e-protocol, not Matcha UI | plugin-e2e-ui private | unit; real UI file sent but not observed in plugin evidence |
| `Quote` | converter/unit; real UI reply not completed | unit; real UI reply not completed | plugin-e2e-protocol | converter/unit; real UI quote not completed | unit/API-backed quote lookup; real UI quote not completed |
| `Face` | not-supported as common `Face` | not-supported as common `Face` | plugin-e2e-protocol | UI emoji becomes `Plain` (`[smile]` text), not `Face` | not-supported as common `Face` |
| `Forward` | not-supported inbound | not-supported inbound | unit; Matcha forward UI/action blocked | not-supported inbound | not-supported inbound |
| Mixed chain | group `At + Plain`; media tested as separate messages | not completed inbound | plugin-e2e-protocol | media tested as separate messages; mixed inbound not completed | unit only |

## Message Send Components

| Component | Telegram | Discord | aiocqhttp | DingTalk | Lark / Feishu |
|-----------|----------|---------|-----------|----------|---------------|
| `Plain` | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound |
| `At` | plugin-e2e-outbound equivalent | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound fallback/equivalent | plugin-e2e-outbound |
| `AtAll` | plugin-e2e-outbound fallback | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound fallback | unit; group live not completed |
| `Image` | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound |
| `Voice` | not-supported in current send converter | not-supported as native voice | converter path; not completed against Matcha UI | fallback as file/text depending DingTalk media support | converter path; live not completed |
| `File` | plugin-e2e-outbound | plugin-e2e-outbound | blocked by Matcha endpoint error | plugin-e2e-outbound | plugin-e2e-outbound |
| `Quote` | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound fallback | plugin-e2e-outbound fallback |
| `Face` | not-supported | not-supported | plugin-e2e-outbound attempted in mixed chain | fallback text | not-supported |
| `Forward` | flattened fallback | flattened fallback | blocked by Matcha unsupported action | flattened fallback | plugin-e2e-outbound flattened fallback |
| Mixed chain | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound except blocked file/forward | plugin-e2e-outbound | plugin-e2e-outbound |

## Event Acceptance

| Event category | Telegram | Discord | aiocqhttp | DingTalk |
|----------------|----------|---------|-----------|----------|
| `message.received` | plugin-e2e-ui | plugin-e2e-ui | plugin-e2e-ui and plugin-e2e-protocol | plugin-e2e-ui private |
| `message.edited` | implemented/unit, not plugin-e2e-ui | historical/direct only, not latest plugin-e2e | unit | not declared |
| `message.deleted` | implemented/unit, not plugin-e2e-ui | historical/direct only, not latest plugin-e2e | unit | not declared |
| `message.reaction` | implemented/unit, not plugin-e2e-ui | historical/direct only, not latest plugin-e2e | not-supported in standard OneBot message path | not declared |
| member join/left/ban | implemented/unit or blocked without disposable users | blocked without disposable users | unit; Matcha fixture unavailable | not declared |
| bot invited/removed | invite plugin-e2e-ui for Telegram; removal blocked | invite historical/plugin-series; removal blocked | unit; Matcha fixture unavailable | not declared |
| requests/friend events | not applicable | not applicable | unit; Matcha fixture unavailable | not declared |
| `platform.specific` | implemented; not latest plugin-e2e | not latest plugin-e2e | adapter lifecycle observed; plugin focus was message path | declared for fallback; not reproduced in UI run |

## Common API Acceptance

| API area | Telegram | Discord | aiocqhttp | DingTalk |
|----------|----------|---------|-----------|----------|
| send/reply | plugin-e2e-outbound | plugin-e2e-outbound | plugin-e2e-outbound, with Matcha file/forward gaps | plugin-e2e-outbound |
| edit/delete | historical/direct or unit; destructive/current UI not repeated | historical/direct; destructive/current UI not repeated | unit/destructive blocked | not declared or blocked |
| message lookup | not-supported | not-supported | plugin-e2e | inbound cache-backed where available; limited live coverage |
| group info/member info | plugin-e2e safe subset | plugin-e2e safe subset | plugin-e2e safe subset | private path only; group not completed |
| user/friend info | plugin-e2e where platform allows | plugin-e2e where platform allows | plugin-e2e | plugin-e2e private user |
| moderation/leave | blocked without disposable safe targets | blocked without disposable safe targets | blocked without disposable safe targets | blocked/not declared |
| `get_file_url` | implemented; latest inbound `File` carried downloadable file data in plugin evidence | URL passthrough for attachments; inbound attachment not completed | not portable/endpoint-dependent | implemented through DingTalk media API; latest inbound `File` carried a platform file URL |
| `call_platform_api` | plugin-e2e safe actions | plugin-e2e safe actions | plugin-e2e safe actions, Matcha gaps documented | plugin-e2e safe `check_access_token` |

## Platform-Specific API Acceptance

| Adapter | plugin-e2e verified | Blocked or not reproduced |
|---------|---------------------|---------------------------|
| Telegram | safe chat/admin/member count/chat-action actions | mutating actions and callback-only actions were not repeated |
| Discord | safe channel/guild/role/typing actions | mutating pin/reaction/invite actions were not repeated in the latest plugin run; inbound attachment paths not completed |
| aiocqhttp | safe OneBot actions such as status/version/can-send checks | `get_group_honor_info` unsupported by Matcha; admin/card/title/ban/record/file/forward require better endpoint fixtures |
| DingTalk | `check_access_token`; real inbound file produced a file URL in the common `File` component | separate media-download replay APIs and group actions need a working follow-up fixture |

## SDK API Acceptance

`EBAEventProbe` exercised the standalone runtime path for:

- bot discovery and bot info lookup
- send message
- component sweep where enabled
- platform API sweep where enabled
- plugin storage
- workspace storage
- plugin/command/tool/knowledge-base list APIs

The probe logs set `ok=true` when the sweep completed with only expected unsupported/blocked items. Individual call details are stored in the JSONL evidence files.

## Residual Risks And Required Follow-Up

- Discord still requires real UI inbound image/file upload evidence before it can be called media-complete.
- aiocqhttp has rich inbound component evidence only at the OneBot reverse WebSocket boundary; Matcha UI did not provide image/file upload coverage.
- DingTalk group trigger remains unclosed; current evidence is private chat only.
- Lark / Feishu requires a clean follow-up live pass: the latest LangBot organization WebSocket run connected, but UI-sent text/image/file after the loop-scheduling fix did not append plugin events.
- Discord UI retry on May 10, 2026 was blocked by the client keeping the send button disabled even after text was entered.
- Destructive moderation and leave APIs are intentionally blocked until disposable users/groups are available.

## Conclusion

The EBA conversion path is implemented and partially proven for the migrated adapters. Telegram and DingTalk now have real UI private-chat image/file inbound evidence. Discord, aiocqhttp, and Lark / Feishu still have explicit UI-level media gaps, so the overall adapter set remains partial acceptance rather than production-complete media acceptance.

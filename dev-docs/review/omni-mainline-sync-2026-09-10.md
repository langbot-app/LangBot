# Legacy and Omni adapter mainline audit

Audit date: 2026-09-10.

- Destination: `dev/4.11.x`, starting at `5ba25c39af85844283f7049beddc54ea71afea76`.
- Upstream: refreshed `origin/master`, `ce6b647fe7e620031c3dd9d16a8e8c08ba13b4b1`.
- Scope: adapter changes since the first Omni fork in March 2026, including shared platform clients, configuration manifests, and shutdown/resource handling.
- Existing local changes, including the Omni identifier rename, are preserved.

The two implementations do not inherit behavior automatically. A commit in `sources/` does not update `adapters/`. The audit compares the current legacy source with master, then checks its actual equivalent in the Omni converter, transport, client, configuration, and lifecycle code. Native interaction handling continues to use `interaction.request` and typed callbacks; old Dify runner-private state is not copied into the new event architecture.

## Platforms with an Omni adapter

| Platform | Relevant mainline work | Legacy result | Omni result |
| --- | --- | --- | --- |
| OneBot / aiocqhttp | JSON cards (`c75890874`, `0963fd544`), base64 (`ccc51522c`), group metadata (`cc7a13158`), listener lifecycle (`2c3e52c16`), bounded lookups (`e1ac5e0fc`), original image URLs (`463b12092`) | Already present | Added JSON-card parsing and normalization for image, voice, and file payloads. Reused the cached, timeout-bounded group/member lookup per adapter instance. Preserved native handler registration, typed events, and original image URLs. |
| Telegram | Streaming (`0755beebc`), bounded media/state (`e1ac5e0fc`), token-bearing image URLs (`9df021eb8`) | Already present | Shares the legacy message converter; ported persistent-message streaming, throttling/size fallback, bounded state, and shutdown. Token-bearing download URLs remain absent from the public Image component. |
| Discord | Streaming (`0755beebc`), media/resource limits (`e1ac5e0fc`), original image URLs (`463b12092`) | Already present | Added snapshot-based send/edit streaming with bounded state. Enforced the mainline media limit on Omni image, voice, and file loading. Incoming public attachment URLs are preserved. |
| Feishu / Lark | Files (`e06fac2bb`), proactive sends (`3680a8024`), service domain (`c7cb42bd7`), tables (`1d15798e5`), nonblocking connection discovery (`48952206d`), resource bounds (`e1ac5e0fc`), final duplicate text (`5ca30133a`), feedback association (`f8010a20e`) | Applied final-text fix; retained the newer SDK cache-task cleanup | Added identical domestic/international/custom domain fields and applied the selected domain to both HTTP and WebSocket clients. Reused nonblocking connection discovery and bounded upload helpers; bounded incoming downloads and callback tasks. Added table cards and feedback-to-monitoring association. The final card contains one text element and exits streaming mode; it does not use the legacy duplicate-placeholder layout. |
| DingTalk | Voice recognition (`de4d14fee`), files (`e06fac2bb`), interactive cards (`0755beebc`), task/card bounds (`e1ac5e0fc`), automatic layout (`8cf001550`) | Applied layout fix in the shared client | Shared client fix reaches both `create_and_card` and native interaction cards. Retained typed file/voice conversion and native callbacks, bounded normal stream cards, cleared callback/card state on shutdown, and exposed the template download. |
| QQ Official | Optional token (`cb45807b1`), Markdown (`c87548c0b`), complete stream snapshots (`79634772d`), resource bounds (`e1ac5e0fc`), original image URLs (`463b12092`) | Applied optional-token fix | Removed the token requirement in constructor and manifest. Added Markdown configuration and sending. Stream and non-stream fallback replace full snapshots instead of appending deltas. Restored original image URLs, bounded state, and closed the owned client on shutdown. |
| WeCom application | Media ID key (`d942bfe19`), original image URLs (`463b12092`), client lifetime (`e1ac5e0fc`) | Applied the `media_id` send fix | Media dispatch already used `media_id`; restored original image URLs and client shutdown. |
| WeCom AI Bot | WS/files/feedback (`d9378c3a8`, `14b1e0d33`, `c7efa4dd7`, `83ccb33fd`), sandbox media (`e934f08ad`), WS loading (`e69a80f5e`) | Already present | Outbound conversion now retains media items. Replies and final stream chunks use the shared upload/reply implementation instead of `[Image]` / `[File]` placeholders. Existing native inbound file/voice/quote handling, feedback, and shared WS fixes remain active. |
| WeCom customer service | Proactive text (`13dba887d`), `open_kfid` and unique outbound `msgid` (`cabde423a`), client limits (`e1ac5e0fc`) | Already present | Existing target parsing and generated outbound message IDs already match. Added owned-client shutdown and cache clearing; removed a shadowed obsolete image-send definition, retaining the bounded active implementation. |
| Slack | Original image URLs (`463b12092`), shared HTTP session (`e1ac5e0fc`) | Already present | Restored original image URLs alongside downloaded data. Existing shared-client behavior remains active; bounded retained typed-event caches. |
| KOOK | Bounded gateway decompression, HTTP responses, and shared sessions (`e1ac5e0fc`) | Already present | Reuses the bounded gateway decoder off the event loop and limited JSON response reader. Existing URL-based image conversion does not eagerly download media. |
| WeChat Official Account | Resource/state cleanup (`e1ac5e0fc`) and outbound IP display (`bca710dbd`) | Already present | Calls the shared client's cleanup on shutdown, bounds typed-event caches, and exposes the outbound IP configuration field. |

All 12 Omni manifests include the corresponding legacy configuration field names and current deployment help links. The Feishu/Lark `domain` and `custom_domain` fields are structurally identical, including labels, descriptions, options, defaults, and conditional display. Display names are unchanged.

## Platforms with no separate Omni implementation

| Platform | Result |
| --- | --- |
| Matrix | Applied `fc1c99843` to fix the unbound logout command during re-login. Existing connection/media/resource fixes already match master. |
| Mattermost | Added the complete mainline adapter, manifest, icon, and regression tests from `d6443b10b`. |
| LINE | Stable source-based sessions (`777fe1f20`), mention conversion (`855ae2bdb`), and resource limits already match master. |
| OpenClaw Weixin | Mainline adapter, outbound IP display, and resource/lifecycle changes already present. |
| WeChatPad | Mainline media/download and resource/lifecycle changes already present. |
| Satori | Mainline lifecycle/resource changes already present. |
| HTTP Bot | Mainline standalone HTTP integration and workspace/resource changes already present. |
| WebPage Bot | Delegated stream helpers and embedded-session behavior already match master. |
| WebSocket / browser debug | Mainline session isolation, scoped history, resource bounds, and routing work already present. Retained 4.11's image-reference retention and pipeline metadata additions. |
| Archived Gewechat, Nakuru, QQBotPy sources | Mainline source changes already present; no separate Omni counterpart exists. |

Documentation-link updates `1cfe87186` and `ec63978ec` were also applied to legacy manifests and matching Omni manifests.

## Intentional architectural differences

- New typed events and platform APIs remain in the Omni modules. Legacy Pipeline message/context conversion stays in the established compatibility path.
- Native interaction delivery uses the generic interaction request/callback protocol. The current 4.11 pipeline/provider code no longer emits `_form_data` or `_resume_from_form`; copying old Dify callback internals would reconnect the wrong execution model.
- This audit establishes parity for the mainline changes in scope, not a claim that every pre-fork legacy-only extension has a typed Omni API. For example, Discord voice-channel management still belongs to the legacy source; sending voice attachments and the post-fork streaming/resource fixes are covered here.
- Shared platform clients retain 4.11-specific return values and additional APIs instead of being overwritten with entire master files.

## Verification

- Full backend unit suite: **3751 passed, 1 skipped**. This includes platform transport tests, Pipeline/event routing, service validation, plugin actions, workspace isolation, and resource handling.
- Dedicated mainline-parity regression suite: **62 passed**. Coverage for configuration coverage, OneBot JSON/base64/metadata, QQ Markdown/snapshots, WeCom media replies, bounded media/gateway reads, lifecycle cleanup, streaming, and Feishu/Lark region selection.
- Ruff formatting and checks pass on the affected Python files.
- Restarted the local backend on port 5399; `/healthz` returns success and reports the plugin runtime connected. All 12 Omni icon endpoints and the new Mattermost icon return HTTP 200.
- Vendor requests in automated tests are mocked. Real delivery to every external platform has not been tested. The instance contains pre-existing incomplete Feishu and WeCom AI Bot configurations; the same missing-credential errors were present before this audit.

Tests: `tests/unit_tests/platform/test_omni_mainline_parity.py`, the platform-specific test files, and the imported Mattermost/WeCom/Lark/DingTalk regressions.

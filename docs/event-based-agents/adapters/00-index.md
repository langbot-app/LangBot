# EBA Adapter Migration Records

This directory records adapter-level migration details for the Event-Based Agents architecture. Each adapter document should be kept close to the implementation and must answer four questions:

1. What changed in the adapter structure.
2. Which configuration fields are required.
3. Which events and APIs are supported.
4. What has been verified end to end.

## Adapter Documents

General acceptance checklist: [EBA Adapter Acceptance Checklist](./acceptance-checklist.md)

Current acceptance report: [EBA Adapter Acceptance Report](./acceptance-report.md)

| Adapter | Status | Document |
|---------|--------|----------|
| Telegram | Migrated; partial plugin E2E, media-inbound gaps remain | [Telegram](./telegram.md) |
| Discord | Migrated; partial plugin E2E, media-inbound gaps remain | [Discord](./discord.md) |
| OneBot v11 / aiocqhttp | Migrated; Matcha UI plus protocol-level multi-component coverage | [OneBot v11 / aiocqhttp](./aiocqhttp.md) |
| DingTalk | Migrated; partial plugin E2E, group/media-inbound gaps remain | [DingTalk](./dingtalk.md) |

## Documentation Checklist

When migrating a new adapter, add one document here with:

- Configuration table matching the adapter manifest.
- Supported event list.
- Supported common API list.
- Supported `call_platform_api` action list.
- Known unsupported APIs and the reason.
- Live test notes, including platform, channel type, destructive operations, and residual risks.
- A clear distinction between real UI inbound media, protocol-level injected inbound media, and bot outbound media.

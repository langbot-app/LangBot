# EBA Adapter Migration Records

This directory records adapter-level migration details for the Event-Based Agents architecture. Each adapter document should be kept close to the implementation and must answer four questions:

1. What changed in the adapter structure.
2. Which configuration fields are required.
3. Which events and APIs are supported.
4. What has been verified end to end.

## Adapter Documents

| Adapter | Status | Document |
|---------|--------|----------|
| Telegram | Migrated and live-tested | [Telegram](./telegram.md) |
| Discord | Migrated and live-tested | [Discord](./discord.md) |

## Documentation Checklist

When migrating a new adapter, add one document here with:

- Configuration table matching the adapter manifest.
- Supported event list.
- Supported common API list.
- Supported `call_platform_api` action list.
- Known unsupported APIs and the reason.
- Live test notes, including platform, channel type, destructive operations, and residual risks.

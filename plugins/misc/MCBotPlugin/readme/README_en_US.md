# MCBotPlugin

A LangBot plugin for Minecraft server chat groups: bind a Minecraft server to your group, query live server status and online players, and track per-player playtime.

> This is the migration of the legacy [MCBotPlugin](https://github.com/langbot-app/MCBotPlugin) (built for QChatGPT) to the new LangBot plugin SDK. MongoDB storage is replaced by the built-in plugin key-value storage (no external database required), the synchronous `mctools` ping is replaced by async `mcstatus`, and the thread-based playtime routine is replaced by an asyncio background task.

## Features

- **Bind a server**: each group can bind one Minecraft (Java Edition) server
- **Status query**: live MOTD, version, online count and player list
- **Playtime stats**: a background task samples online players and aggregates per-player online time over any period

## Commands

| Command | Description | Privilege |
| --- | --- | --- |
| `!mcbot` | Show help | Everyone |
| `!mcbot bind <address[:port]>` | Bind a server to this group | Admin |
| `!mcbot unbind` | Unbind the server | Admin |
| `!mcbot status` | Show server status and online players | Everyone |
| `!mcbot time [minutes]` | Show playtime stats (default 1440 min = 24h) | Everyone |

> Admins are determined by LangBot's `admins` config (`{launcher_type}_{launcher_id}`).

## Config

| Key | Description | Default |
| --- | --- | --- |
| `track_interval` | Background sampling interval in seconds (min 15) | 60 |
| `ping_timeout` | Server ping timeout in seconds | 10 |

## Dependencies

- [`mcstatus`](https://github.com/py-mine/mcstatus) — Minecraft server status queries

## Storage

Bindings and online records are kept in LangBot's built-in plugin KV storage; no MongoDB needed. Online records are retained for 14 days.

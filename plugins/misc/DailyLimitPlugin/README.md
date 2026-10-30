# Daily Limit Plugin

Limit the number of conversations **per session per day** for LangBot, with a built-in management **Page** to view, configure and reset limits — production ready.

## Features

- **Per-session daily limit** — each private chat / group is counted independently
- **Management Page** (in the LangBot admin panel) to:
  - View every tracked session with today's usage and a progress bar
  - Set the **default limit for new sessions**
  - **Override the limit for individual sessions**
  - **Manually reset** a single session's counter, or reset all at once
  - Stop tracking (remove) a session
  - Edit the limit-reached message, silent mode, reset timezone and reset hour — no restart needed
- **Silent mode** — drop over-limit messages with no reply
- **Timezone-aware reset** — configure the UTC offset and hour for the daily rollover
- **Persistent** — all state is stored in plugin storage and survives restarts

## Components

| Path | Type | Purpose |
|------|------|---------|
| `main.py` | Plugin | Shared state, counting/limit/reset logic, persistence |
| `components/event_listener/` | EventListener | Counts each conversation, blocks when the limit is reached |
| `components/pages/manage/` | Page | Management UI (sessions, defaults, manual reset) |

## Configuration

These are the **initial defaults**; everything is also editable live from the management Page.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `daily_limit` | integer | `50` | Default max conversations per session per day. `0` = unlimited. |
| `limit_message` | string | `您今天的对话次数已达上限，请明天再来吧~` | Message shown when the limit is exceeded. |
| `reset_timezone_offset` | integer | `8` | UTC offset in hours for daily reset (e.g. `8` for UTC+8, `9` for UTC+9). |
| `reset_hour` | integer | `0` | Hour of the day (in configured timezone) when the counter resets. |
| `silent_mode` | boolean | `false` | When enabled, excess messages are silently dropped. |

## How It Works

A **session** is `{type}:{id}` — a specific private chat or group. The EventListener hooks
`PersonNormalMessageReceived` and `GroupNormalMessageReceived`; for every message it checks the
session's counter against its effective limit (per-session override, or the global default).
When the limit is reached it either replies with the limit message or silently drops the message
(silent mode), and blocks the default LLM pipeline.

Counters roll over at the configured hour in the configured timezone. The management Page reads and
mutates the same state via the plugin's `handle_api`, so changes take effect immediately.

State is kept per installation, so the plugin can be placed on a shared worker: see
[SHARED_RUNTIME.md](SHARED_RUNTIME.md).

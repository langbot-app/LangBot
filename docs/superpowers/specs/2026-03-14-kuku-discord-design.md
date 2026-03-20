# KUKU Discord Bot — Engineering Spec

> Superseded on 2026-03-20 by [`docs/kuku-design.md`](../../kuku-design.md)
> Reason: the chosen direction is a LangBot-native KUKU core with Discord as Phase 1 and Feishu as Phase 2, not a standalone Discord-only service.

> Status: Superseded
> Date: 2026-03-14

---

## 1. Overview

KUKU is a standalone Discord bot written in Go. It joins Discord channels, listens to messages, builds per-user memories via Mem0, and uses LangBot's LLM pipeline to generate responses. Its personality emerges organically from accumulated user memories rather than a fixed persona.

**MVP core loop:** ingest messages → build memories → detect silence → generate contextual message → send it. Also responds reactively to @mentions and replies.

---

## 2. Goals & Non-Goals

### Goals (MVP)
- Discord-only bot with full native Discord UX (slash commands, embeds, buttons)
- Silence detection per channel — proactively send a message after N minutes of inactivity
- Reactive responses to @mentions and replies to KUKU messages
- Per-user memory via Mem0 cloud API, injected into every LLM prompt
- Personality derived from user memories, not a fixed persona config
- `/kuku setup`, `/kuku stop`, and `/kuku status` slash commands (admin only)
- Single-container deployment, independent of LangBot's Docker setup

### Non-Goals (MVP)
- Feishu / WeChat support
- Multiple KUKUs per channel
- Discord Activity embedded page
- Persistent channel state across restarts
- External tool calls / agentic tasks

---

## 3. Architecture

Single Go process. All concurrency via goroutines and channels. No message queue, no Redis, no sidecars.

```
Discord (discordgo)
      │
      ├── on_message ──────────────────────────────────────────┐
      │                                                         │
      ├── on_interaction (button clicks, slash commands)        │
      │                                                         ▼
      └── send (embeds, replies, plain text)           internal/bot
                                                            │
                    ┌───────────────────────────────────────┤
                    │               │               │        │
                    ▼               ▼               ▼        ▼
             internal/       internal/       internal/  internal/
              silence         memory          langbot    persona
            (goroutine      (Mem0 REST       (WebSocket   (channel
            per channel)      client)         client)      state)
```

---

## 4. Repository Structure

```
kuku/
├── cmd/
│   └── kuku/
│       └── main.go               # entry point: load config, init components, start bot
├── internal/
│   ├── bot/
│   │   ├── bot.go                # discordgo session, event registration, send helpers
│   │   ├── commands.go           # slash command handlers (/kuku setup, /kuku stop, /kuku status)
│   │   └── handlers.go           # on_message and on_interaction routing
│   ├── silence/
│   │   └── detector.go           # one goroutine per channel, ticker-based silence detection
│   ├── memory/
│   │   └── mem0.go               # Mem0 REST API client: Add() and Search()
│   ├── langbot/
│   │   └── client.go             # WebSocket client to LangBot pipeline, Chat() method
│   └── channel/
│       └── state.go              # ChannelState struct, in-memory map keyed by channelID
├── config/
│   └── config.go                 # Config struct, loaded from env vars
├── go.mod
├── Dockerfile                    # multi-stage build → ~10MB image
└── docker-compose.yml            # single kuku service, env_file: .env
```

---

## 5. Components

### 5.1 `internal/bot`

Owns the `discordgo.Session`. Responsibilities:
- Register slash commands on startup via Discord application commands API
- Route `on_message` events: call `memory.Add`, call `silence.Reset`, check if KUKU should reply (mention or reply-to-KUKU), if so call `langbot.Chat` and send response
- Route `on_interaction` events: handle slash command interactions
- `SendEmbed(channelID, content string)` and `Reply(msg, content string)` helpers

### 5.2 `internal/silence`

One goroutine per active channel. On each tick (every 60s), checks if `now - lastMessageTime > SilenceThreshold`. If so, and not within quiet hours, fires a callback into `bot` to trigger a proactive message, then resets the timer.

Each goroutine is controlled via a `context.Context` — `Deactivate` cancels the context, which causes the goroutine to exit cleanly. No goroutine leaks.

Quiet hours are evaluated in UTC. Overnight ranges (e.g. `QUIET_HOURS_START=22`, `QUIET_HOURS_END=6`) are supported: the check is `hour >= start || hour < end`.

```go
type Detector struct {
    channels map[string]*channelTimer  // channelID → timer state
    mu       sync.Mutex
}

type channelTimer struct {
    lastMessage time.Time
    cancel      context.CancelFunc
}

func (d *Detector) Activate(channelID string, cfg SilenceConfig, onFire func(channelID string))
func (d *Detector) Reset(channelID string)
func (d *Detector) Deactivate(channelID string)  // cancels goroutine context
```

### 5.3 `internal/memory`

Thin wrapper over Mem0's REST API. Two operations only.

```go
type Client struct {
    apiKey  string
    baseURL string  // https://api.mem0.ai/v1
    http    *http.Client
}

func (c *Client) Add(userID, message string) error
func (c *Client) Search(userID, query string, limit int) ([]string, error)
```

Failures are logged and silently skipped — KUKU still responds without memories rather than erroring out.

### 5.4 `internal/langbot`

Manages one WebSocket connection per active channel. The connection URL is built once at startup from `LANGBOT_URL` and `LANGBOT_PIPELINE_ID` — all channel connections use the same pipeline, just separate WebSocket sessions.

`Chat` accepts a `context.Context` so callers can set a timeout. If the WebSocket drops while a `Chat` call is in flight, the pending channel is closed and `Chat` returns an error immediately — the caller logs and drops the in-flight message (no retry, no goroutine leak). On reconnect, LangBot starts a fresh session for that channel (prior context is lost — acceptable for MVP).

Each channel connection reconnects independently with exponential backoff (1s, 2s, 4s… max 60s) when it drops outside of a `Chat` call.

```go
// Client manages one WebSocket connection per active channel.
// The base URL (built from LANGBOT_URL + LANGBOT_PIPELINE_ID) is shared across all connections.
type Client struct {
    baseURL string  // ws://LANGBOT_URL/api/v1/pipelines/<PIPELINE_ID>/ws/connect?session_type=group
    apiKey  string
    conns   map[string]*channelConn  // channelID → connection
    mu      sync.Mutex
}

type channelConn struct {
    conn    *websocket.Conn
    pending chan string       // one in-flight request per connection
    cancel  context.CancelFunc
}

// Chat sends prompt to LangBot on the channel's dedicated connection and returns
// the full accumulated LLM response (streaming chunks joined until is_final=true).
// Returns error if ctx is cancelled, times out, or the connection drops mid-flight.
func (c *Client) Chat(ctx context.Context, channelID, prompt string) (string, error)

// Activate opens a WebSocket connection for channelID. Called on /kuku setup.
func (c *Client) Activate(channelID string) error

// Deactivate closes the WebSocket connection for channelID. Called on /kuku stop.
func (c *Client) Deactivate(channelID string)
```

### 5.5 `internal/channel`

In-memory map of active channels and their config. Lost on restart (acceptable for MVP).

Also tracks a rolling message buffer (last 20 messages) and the set of recently active user IDs per channel — both used for prompt construction.

```go
type Message struct {
    UserID      string
    Username    string
    Content     string
    Timestamp   time.Time
}

type State struct {
    Active          bool
    SilenceMinutes  int
    QuietHoursStart int       // hour 0-23, UTC
    QuietHoursEnd   int       // hour 0-23, UTC; overnight ranges supported
    RecentMessages  []Message // ring buffer, max 20
    RecentUserIDs   []string  // deduplicated, last N active users
}

type Store struct {
    mu       sync.RWMutex
    channels map[string]*State  // channelID → state
}
```

---

## 6. Data Flows

### Proactive message (silence fires)

```
silence.Detector fires for channelID
  → channel.Store.Get(channelID) → recentUserIDs, recentMessages
  → for each userID in recentUserIDs: memory.Search(userID, last message content)
  → build prompt: [system instruction] + [memories] + [recentMessages formatted]
  → langbot.Chat(ctx with 30s timeout, channelID, prompt)
  → bot.SendEmbed(channelID, response)
  → silence.Reset(channelID)
```

### Reactive message (@mention or reply to KUKU)

```
discordgo on_message fires
  → channel.Store.AppendMessage(channelID, userID, username, content)
  → memory.Add(userID, message content)
  → silence.Reset(channelID)
  → if @mention or reply-to-KUKU:
      memory.Search(userID, message content)
      → recentMessages = channel.Store.Get(channelID).RecentMessages
      → build prompt: [system instruction] + [memories] + [recentMessages formatted]
      → langbot.Chat(ctx with 30s timeout, channelID, prompt)
      → bot.Reply(original message, response)
```

### Setup flow

```
admin runs /kuku setup in channel
  → channel.Store.Set(channelID, defaultState)
  → silence.Detector.Activate(channelID, ...)
  → bot.SendEmbed(channelID, intro message)
```

---

## 7. LangBot WebSocket Protocol

Verified against `websocket_chat.py` and `websocket_adapter.py` in the LangBot source.

```
Connect:
  ws://<LANGBOT_URL>/api/v1/pipelines/<LANGBOT_PIPELINE_ID>/ws/connect?session_type=group

On connect, receive:
  { "type": "connected", "connection_id": "...", "pipeline_uuid": "...", "session_type": "group", "timestamp": "..." }

Send message:
  {
    "type": "message",
    "message": [{ "type": "Plain", "text": "<prompt>" }],
    "stream": true
  }

Receive (streaming chunk, is_final=false):
  { "type": "response", "session_type": "group", "data": { "id": 1, "role": "assistant", "content": "...", "is_final": false, ... } }

Receive (final chunk, is_final=true):
  { "type": "response", "session_type": "group", "data": { "id": 1, "role": "assistant", "content": "...", "is_final": true, ... } }

Receive error:
  { "type": "error", "message": "..." }
```

**Key notes from source:**
- The message body uses a `message` field containing a LangBot `MessageChain` array (not a plain `content` string)
- LangBot streams responses as multiple `response` frames; KUKU should accumulate chunks until `is_final: true`
- **Channel isolation: one WebSocket connection per active channel.** LangBot maintains per-connection session history, so each channel gets its own connection. The `langbot.Client` manages a map of `channelID → *websocket.Conn`.
- The `connection_id` in the connect response is LangBot's internal ID; KUKU does not need to track it

---

## 8. Prompt Construction

Assembled in `bot` before every `langbot.Chat` call:

```
You are KUKU, a member of this Discord group. You are not a bot or assistant.
You talk like a real person — casual, direct, sometimes funny.
Never say you are an AI. Never offer to help. Just vibe.

What you know about the people here:
<mem0 search results for relevant users; omit this section entirely if no memories found>

Recent conversation:
<last 20 messages from channel.State.RecentMessages, formatted as "username: message">

<either the user's message, or "The group has been quiet for a while. Say something natural to restart the conversation.">
```

---

## 9. Config

All configuration via environment variables:

| Variable | Description | Default |
|---|---|---|
| `DISCORD_TOKEN` | Bot token | required |
| `DISCORD_APP_ID` | Application ID for slash command registration | required |
| `LANGBOT_URL` | LangBot base URL | `http://localhost:5300` |
| `LANGBOT_API_KEY` | LangBot API key | required |
| `LANGBOT_PIPELINE_ID` | Pipeline UUID | required |
| `MEM0_API_KEY` | Mem0 cloud API key | required |
| `SILENCE_MINUTES` | Minutes of inactivity before KUKU speaks | `30` |
| `QUIET_HOURS_ENABLED` | Whether to enforce quiet hours | `false` |
| `QUIET_HOURS_START` | Hour (UTC, 0-23) to stop proactive messages. Overnight ranges supported (e.g. 22 start, 6 end). Ignored if `QUIET_HOURS_ENABLED=false`. | `0` |
| `QUIET_HOURS_END` | Hour (UTC, 0-23) to resume proactive messages. Ignored if `QUIET_HOURS_ENABLED=false`. | `8` |

---

## 10. Error Handling

| Failure | Behaviour |
|---|---|
| LangBot WebSocket drops | Reconnect with exponential backoff (1s, 2s, 4s… max 60s). Silence detector keeps running. |
| Mem0 API fails | Log error, skip memory injection. KUKU responds without memories. |
| Discord rate limit | `discordgo` handles automatically. |
| KUKU process crashes | Docker `restart: unless-stopped` brings it back. Channel state resets (acceptable for MVP). |

---

## 11. Deployment

**`docker-compose.yml`:**
```yaml
services:
  kuku:
    build: .
    restart: unless-stopped
    env_file: .env
```

**`Dockerfile`** (multi-stage):
```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o kuku ./cmd/kuku

FROM alpine:3.21
COPY --from=builder /app/kuku /kuku
ENTRYPOINT ["/kuku"]
```

Single container, ~10MB image. No sidecars. Mem0 is cloud-hosted, LangBot runs separately.

---

## 12. Dependencies

| Package | Purpose |
|---|---|
| `github.com/bwmarrin/discordgo` | Discord bot, slash commands, embeds, interactions |
| `github.com/gorilla/websocket` | WebSocket client to LangBot |
| Standard `net/http` | Mem0 REST API calls |
| Standard `encoding/json` | JSON serialisation |
| Standard `os` / `strconv` | Config from env vars |

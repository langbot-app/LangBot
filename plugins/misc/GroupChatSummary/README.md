# GroupChatSummary

Summarize group chat messages using LLM. Never miss important discussions again.

## Features

- **Message Collection**: Automatically records all group messages
- **Manual Summary**: Use `!summary` command to get instant summaries
- **Time-based Summary**: Summarize messages from the last N hours
- **LLM Tool**: AI can call the summary tool when users ask "what did I miss?"
- **Auto Summary**: Optionally trigger summaries after N messages accumulate
- **Persistent Storage**: Message history survives plugin restarts

## Commands

| Command | Description |
|---------|-------------|
| `!summary [count]` | Summarize recent N messages (default: 100) |
| `!summary hours <N>` | Summarize messages from last N hours |
| `!summary status` | Show message buffer status |
| `!summary clear` | Clear stored messages |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| Max Messages | 500 | Maximum messages stored per group |
| Default Summary Count | 100 | Messages to summarize by default |
| Auto Summary | Off | Auto-summarize every N messages |
| Auto Summary Threshold | 200 | Messages before auto-trigger |
| Language | Chinese | Summary output language |

## How It Works

1. The plugin listens to all group messages and stores them in memory (persisted to storage)
2. When triggered (command, tool call, or auto), it formats the messages and sends them to your configured LLM
3. The LLM generates a structured summary with key topics, decisions, and action items

## Example

```
User: !summary 50
Bot: ⏳ Summarizing 50 messages...
Bot: 📋 Group Chat Summary

**Project Discussion**
- Team decided to use React for the frontend
- Backend API deadline moved to next Friday

**Action Items**
- @Alice: Prepare design mockups by Wednesday
- @Bob: Set up CI/CD pipeline
```

## Shared runtime

`manifest.yaml` declares `sharedRuntime: shared-runtime-v1` +
`componentModel: stateless-v1`, so this plugin can be placed on a multi-tenant
shared worker: config is read per invocation, message buffers are keyed by
installation binding and loaded on demand, and the detached auto-summary task is
stopped in `on_installation_revoked`. See
[SHARED_RUNTIME.md](SHARED_RUNTIME.md) for the details and known limits. This
source is not certified.

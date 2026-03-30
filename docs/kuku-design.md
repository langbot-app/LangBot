# KUKU AI Agent — Engineering Design Doc

> Based on KUKU AI Agent IP PRD v1.0
> Status: Approved target architecture
> Last updated: 2026-03-28

---

## 1. Overview

KUKU is a family of AI Agent IPs. Each KUKU is a digital group member with a distinct personality that can be added to Discord group chats (guild channels). It perceives group atmosphere, proactively initiates conversation when the group goes silent, and builds a dynamic memory of each member over time.

The implementation direction is:

- Build KUKU as a LangBot-native capability with a shared core
- Ship Discord as the only platform in scope for this design
- Keep platform-specific logic behind LangBot adapters so additional IM channels could be integrated later without rewriting the KUKU core (no Feishu or other platform work is planned here)

**MVP core loop:** detect group silence -> generate a natural conversation opener -> send it -> repeat.

## 1.1 Current implementation status

The repository does not implement the full KUKU runtime described below yet.

What exists today:

- persisted KUKU group settings in `kuku_group_settings`
- KUKU setup/read APIs under `/api/v1/kuku/...`
- Discord-only validation for the current MVP boundary
- one fixed persona, `kuku-sunny`
- in-process KUKU runtime (`KukuRuntime`): per-channel human activity tracking on Discord, periodic silence checks, `quiet_hours` / `cooldown_minutes`, LLM opener via the bot’s pipeline `local-agent` model, `send_message` to the Discord channel

What does not exist yet:

- Mem0 (or equivalent) message memory and recall
- LangBot plugin packaging for KUKU (runtime is host-native for now)
- user profile builder and richer persona flows
- non-Discord platform adapters for KUKU

Read the rest of this document as the approved target design, not as a statement that every component already exists in the codebase.

---

## 2. Goals & Non-Goals

### Goals (MVP)

- Deploy a KUKU bot to a Discord channel
- Detect silence (no messages for N minutes) and proactively send a message
- Accumulate per-user memory and inject it into every KUKU response
- Use one fixed KUKU persona across the MVP

### Non-Goals (MVP)

- Multiple KUKUs in the same group simultaneously
- Persona selection or persona changes after deployment
- Discord Activity embedded page (P1)
- Non-Discord IM platforms
- WeChat or other channels not supported by this document
- External tool calls / agentic tasks (post-MVP)

---

## 3. Target Architecture

KUKU should not be implemented as a standalone service outside LangBot. The core behavior must live inside LangBot, and Discord-specific I/O should stay at the adapter boundary.

KUKU is intended to be implemented as a **LangBot Plugin**. LangBot handles platform abstraction, message ingestion, and pipeline execution. The plugin adds KUKU-specific behavior for the Discord adapter path in this design.

```
Discord
      |
      v
 LangBot Core
  |- Platform Adapter (discord)
  |- Message Pipeline
  `- Plugin Runtime
         |
         v
    KUKU Plugin
     |- SilenceDetector       - background scheduler per group
     |- MemoryManager         - per-user Mem0 storage
     |- UserProfileBuilder    - extracts traits from messages
     `- KUKUResponder         - injects profile + persona -> LLM -> send
```

### Component responsibilities


| Component            | Responsibility                                                                |
| -------------------- | ----------------------------------------------------------------------------- |
| `SilenceDetector`    | Track last message time per group; fire callback when threshold exceeded      |
| `MemoryManager`      | Wrap Mem0; store every incoming message; retrieve relevant memories on demand |
| `UserProfileBuilder` | Periodically run LLM over recent messages to extract structured user traits   |
| `KUKUResponder`      | Build the final prompt (persona + memories + context) and call the LLM        |


### Platform strategy

- Shared KUKU core owns silence detection, memory, prompt construction, and response policy
- Discord is the only platform in scope; all setup UX, message formatting, and permission handling for KUKU target Discord
- Platform-specific setup UX, message formatting, and permission handling must stay outside the shared core

---

## 4. Platform Support


| Platform | Bot type                | Message format                  | Config flow                                           |
| -------- | ----------------------- | ------------------------------- | ----------------------------------------------------- |
| Discord  | Bot (P0), Activity (P1) | Embed cards + button components | Admin adds bot and enables KUKU for the channel/group |


This document does not specify Feishu or other IM platforms. KUKU logic is written to stay independent of Discord presentation details where possible, but only Discord is in scope for implementation and milestones below.

---

## 5. Core Features

### 5.1 Silence Detection

Monitor the last message timestamp per group. When the gap exceeds the configured threshold, trigger KUKU to speak.

```python
SILENCE_THRESHOLD = timedelta(minutes=30)  # configurable per group

class SilenceDetector:
    def __init__(self):
        self.last_message_time: dict[str, datetime] = {}

    def on_message(self, group_id: str):
        self.last_message_time[group_id] = datetime.now()

    async def watch(self, group_id: str, kuku_callback: Callable):
        while True:
            await asyncio.sleep(60)  # poll every minute
            last = self.last_message_time.get(group_id)
            if last and datetime.now() - last > SILENCE_THRESHOLD:
                await kuku_callback(group_id)
                # reset timer to avoid spam
                self.last_message_time[group_id] = datetime.now()
```

**Considerations:**

- Add jitter to the trigger time so KUKU doesn't always fire at exactly T+30m
- Respect quiet hours (configurable per group, e.g. 00:00–08:00 local time)
- Back off if the previous proactive message was ignored (no replies within 10 min)

### 5.2 Proactive Topic Generation

When silence is detected, KUKU generates an opening message using:

- The fixed KUKU persona prompt
- The last N messages as context
- Relevant user profile snippets for active members

```python
async def generate_opener(
    group_id: str,
    persona: KUKUPersona,
    recent_messages: list[Message],
    user_profiles: dict[str, UserProfile],
) -> str:
    context = format_message_history(recent_messages)
    profiles = format_relevant_profiles(user_profiles, recent_messages)

    prompt = f"""
{persona.system_prompt}

Recent group conversation:
{context}

What you know about the people in this group:
{profiles}

The group has gone quiet. Generate one natural, in-character message to restart the conversation.
Keep it short (1-2 sentences). Don't be cringe. Match the group's energy.
"""
    return await llm.complete(prompt)
```

### 5.3 Reactive Responses

When a user directly @mentions KUKU or replies to a KUKU message, respond immediately using the same prompt structure (persona + user memories + conversation context).

### 5.4 MVP rollout

Phase 1:

- Discord only
- One fixed KUKU persona
- Proactive silence-breaking messages
- Reactive replies on mention or reply

Phase 2 (examples — platform TBD if the product expands later):

- Optional: second LangBot-supported platform using the same plugin core
- Same persona, memory, and silence logic; new adapter and setup UX only

---

## 6. Memory & User Profile System

### 6.1 Memory Layer — Mem0 (MVP)

Use [Mem0](https://github.com/mem0ai/mem0) as the memory backend. It handles:

- Per-`user_id` storage
- Automatic fact extraction from raw messages ("user is a developer", "user likes anime")
- Deduplication
- Relevance-ranked retrieval

```python
from mem0 import Memory

class MemoryManager:
    def __init__(self, store_config: dict):
        self.memory = Memory.from_config(store_config)

    def ingest(self, user_id: str, message: str, group_id: str):
        """Call this for every message seen in the group."""
        self.memory.add(
            message,
            user_id=user_id,
            metadata={"group_id": group_id}
        )

    def recall(self, user_id: str, query: str, limit: int = 5) -> list[str]:
        """Retrieve memories relevant to the current context."""
        results = self.memory.search(query, user_id=user_id, limit=limit)
        return [r["memory"] for r in results]
```

**Storage backend:** For production, configure Mem0 with Postgres (facts) + Qdrant (vectors). Do not use in-memory storage.

### 6.2 User Profile Schema

```python
@dataclass
class UserProfile:
    user_id: str
    platform: str              # "discord" for this design
    group_id: str
    display_name: str
    personality_tags: list[str]   # e.g. ["sarcastic", "tech-savvy"]
    interests: list[str]          # e.g. ["gaming", "k-pop"]
    key_memories: list[str]       # e.g. ["mentioned moving to SF in Jan"]
    last_active: datetime
    message_count: int
    created_at: datetime
    updated_at: datetime
```

### 6.3 Profile Building Pipeline

Profiles are built in two ways:

1. **Passive (real-time):** Every message is passed to `MemoryManager.ingest()`. Mem0 continuously extracts and stores facts.
2. **Active (batch):** A background job runs every 24 hours per active user. It feeds the last 7 days of that user's messages to an LLM and asks it to update `personality_tags` and `interests` in the `UserProfile` record.

```python
async def refresh_user_profile(user_id: str, recent_messages: list[str]) -> UserProfile:
    prompt = f"""
Analyze these messages from a group chat member and extract:
1. Personality traits (max 5 short tags)
2. Interests / topics they talk about (max 5)
3. Any notable facts worth remembering

Messages:
{chr(10).join(recent_messages)}

Respond in JSON.
"""
    result = await llm.complete(prompt, response_format="json")
    return merge_into_profile(user_id, result)
```

### 6.4 Prompt Injection

Every KUKU response (proactive or reactive) injects relevant user context:

```python
def build_system_prompt(
    persona: KUKUPersona,
    active_users: list[UserProfile],
    recalled_memories: dict[str, list[str]],
) -> str:
    user_context = ""
    for user in active_users:
        memories = recalled_memories.get(user.user_id, [])
        if memories:
            user_context += f"\n- {user.display_name}: {', '.join(memories)}"

    return f"""
{persona.system_prompt}

People in this group you know:{user_context if user_context else " (no memories yet)"}
"""
```

---

## 7. Persona System

Each KUKU character is defined by a `KUKUPersona` config:

```python
@dataclass
class KUKUPersona:
    id: str                    # e.g. "kuku-sunny"
    name: str                  # display name
    avatar_url: str
    tags: list[str]            # e.g. ["cheerful", "energetic"]
    tagline: str               # one-line description shown at selection
    system_prompt: str         # the core persona instruction
    silence_trigger_style: str # how it breaks silence: "question" | "observation" | "meme"
```

Persona parameters can be **micro-adjusted** over time based on group style analysis, but the core `system_prompt` is fixed until the bot is re-added.

---

## 8. Setup Flow

### Discord (P0 — slash command)

1. Admin invites KUKU bot to server
2. Admin runs `/kuku setup` in target channel
3. Bot responds with persona selection embed (buttons)
4. Admin clicks persona → bot confirms and activates

### Discord (P1 — Activity)

1. Admin opens Activity in channel → KUKU selection web page loads inside Discord
2. Admin selects persona → OAuth authorization → bot activates
3. Requires advance Discord Activity approval (apply early)

---

## 9. Data Flow Diagram

```
User sends message in group
         │
         ▼
LangBot platform adapter receives event
         │
         ├──► SilenceDetector.on_message(group_id)   [reset timer]
         │
         └──► MemoryManager.ingest(user_id, message)  [store facts]

--- N minutes pass with no messages ---

SilenceDetector fires callback
         │
         ▼
Fetch recent_messages (last 20) from platform API
         │
         ▼
For each active user in recent messages:
  MemoryManager.recall(user_id, context_query)
         │
         ▼
KUKUResponder.build_prompt(persona, memories, context)
         │
         ▼
LLM call → opener message
         │
         ▼
Platform adapter sends message to group
```

---

## 10. Build Order (Recommended)


| Week | Milestone                                                                                |
| ---- | ---------------------------------------------------------------------------------------- |
| 1    | LangBot plugin skeleton; Discord bot in server/channel echoes messages                   |
| 2    | Mem0 integration; every message stored; basic memory recall working                      |
| 3    | Silence detector; proactive message generation with persona prompts                      |
| 4    | User profile builder (batch job); profile injection into prompts; persona selection flow |
| 5    | Tuning, edge cases, quiet hours, anti-spam backoff                                       |
| P1   | Discord Activity embedded config page                                                    |


---

## 11. Open Questions

1. **OpenClaw dependency** — The PRD describes KUKU as "based on OpenClaw" but lists LangBot as the recommended framework. Clarify: is OpenClaw a separate agent runtime layer on top of LangBot, or is LangBot replacing it for MVP?
2. **Discord history backfill** — Building profiles from *existing* group history (before the bot was added) requires reading channel message history via the Discord API. This needs `MESSAGE_CONTENT` privileged intent, which requires bot verification for servers with 100+ members. Plan for this early.
3. **Mem0 storage backend** — Decide on Postgres + Qdrant vs. hosted Mem0 cloud for production. Self-hosted is cheaper and keeps data in-house; hosted is faster to set up.
4. **OpenClaw deployment model** — Cloud-hosted (we manage) vs. self-hosted per deployer? Affects onboarding complexity significantly.
5. **Rate limiting** — Discord has message rate limits. KUKU should not fire more than once per silence event and must respect platform cooldowns.

---

## 12. Reference Implementations


| Project                                                                  | What to steal                                                       |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| [Mem0](https://github.com/mem0ai/mem0)                                   | Memory layer — use directly                                         |
| [team-memory-bot](https://github.com/rkarwankar/team-memory-bot)         | Mem0 + Discord complete example                                     |
| [MemoryOS](https://github.com/BAI-LAB/MemoryOS)                          | Hierarchical memory architecture reference (short/mid/long-term)    |
| [always-on-agent](https://github.com/randomchaos7800hub/always-on-agent) | Silence detection + proactive trigger pattern                       |
| [Discord-AI-Selfbot](https://github.com/Najmul190/Discord-AI-Selfbot)    | `~analyse` command — user personality analysis from message history |
| [discord.py](https://github.com/Rapptz/discord.py)                       | Discord event handling, Embed, Button components                    |



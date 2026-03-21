# KUKU Discord MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Discord-first KUKU MVP described in [`docs/kuku-design.md`](/Users/shuaiqingluo/Dev/a012tech/LangBot/docs/kuku-design.md): per-channel KUKU activation, silence-triggered proactive messages, mention/reply handling, and user memory-backed prompting.

**Architecture:** Keep KUKU as a LangBot plugin package that lives in this repository under `plugins/kuku/`, and add only the minimum host-side support needed in LangBot core: KUKU group settings persistence, setup/read APIs, Discord history access helpers, and service registration. The plugin owns runtime behavior, scheduling, memory ingestion, prompt building, and persona logic; LangBot core remains the platform host and configuration surface.

**Tech Stack:** Python 3.11+, Quart, SQLAlchemy, `langbot-plugin`, `discord.py`, LangBot persistence/task/runtime services, Mem0 with Postgres + Qdrant-backed storage.

---

## File Structure

**Create**
- `plugins/kuku/pyproject.toml`
- `plugins/kuku/manifest.yaml`
- `plugins/kuku/README.md`
- `plugins/kuku/src/langbot_kuku_plugin/__init__.py`
- `plugins/kuku/src/langbot_kuku_plugin/plugin.py`
- `plugins/kuku/src/langbot_kuku_plugin/config.py`
- `plugins/kuku/src/langbot_kuku_plugin/personas.py`
- `plugins/kuku/src/langbot_kuku_plugin/models.py`
- `plugins/kuku/src/langbot_kuku_plugin/services/silence.py`
- `plugins/kuku/src/langbot_kuku_plugin/services/memory.py`
- `plugins/kuku/src/langbot_kuku_plugin/services/profile.py`
- `plugins/kuku/src/langbot_kuku_plugin/services/responder.py`
- `plugins/kuku/src/langbot_kuku_plugin/services/runtime.py`
- `plugins/kuku/src/langbot_kuku_plugin/components/event_listener.py`
- `plugins/kuku/src/langbot_kuku_plugin/components/command.py`
- `src/langbot/pkg/entity/persistence/kuku.py`
- `src/langbot/pkg/persistence/migrations/dbm025_kuku_group_settings.py`
- `src/langbot/pkg/api/http/service/kuku.py`
- `src/langbot/pkg/api/http/controller/groups/kuku.py`
- `tests/unit_tests/kuku/test_kuku_service.py`
- `tests/unit_tests/kuku/test_discord_runtime_bridge.py`
- `tests/unit_tests/kuku/test_silence_scheduler.py`
- `tests/unit_tests/kuku/test_prompt_builder.py`

**Modify**
- `src/langbot/pkg/core/app.py`
- `src/langbot/pkg/core/stages/build_app.py`
- `src/langbot/pkg/utils/constants.py`
- `src/langbot/pkg/platform/sources/discord.py`
- `src/langbot/pkg/platform/botmgr.py`
- `src/langbot/pkg/entity/persistence/__init__.py`
- `src/langbot/pkg/api/http/controller/groups/__init__.py`
- `src/langbot/templates/config.yaml`
- `docs/kuku-design.md`

## Task 1: Persist KUKU group activation and runtime settings

**Files:**
- Create: `src/langbot/pkg/entity/persistence/kuku.py`
- Create: `src/langbot/pkg/persistence/migrations/dbm025_kuku_group_settings.py`
- Modify: `src/langbot/pkg/entity/persistence/__init__.py`
- Modify: `src/langbot/pkg/utils/constants.py`
- Test: `tests/unit_tests/kuku/test_kuku_service.py`

- [ ] **Step 1: Write the failing persistence/service test**

```python
async def test_upsert_group_settings_persists_persona_and_threshold(kuku_service):
    payload = {
        'bot_uuid': 'bot-1',
        'platform': 'discord',
        'group_id': '123',
        'persona_id': 'kuku-sunny',
        'silence_minutes': 30,
        'quiet_hours': {'start': '00:00', 'end': '08:00', 'timezone': 'UTC'},
        'enabled': True,
    }

    saved = await kuku_service.upsert_group_settings(payload)

    assert saved['bot_uuid'] == 'bot-1'
    assert saved['group_id'] == '123'
    assert saved['persona_id'] == 'kuku-sunny'
    assert saved['silence_minutes'] == 30
    assert saved['enabled'] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit_tests/kuku/test_kuku_service.py::test_upsert_group_settings_persists_persona_and_threshold -v`
Expected: FAIL with import or attribute errors because `KukuService` and the persistence model do not exist yet.

- [ ] **Step 3: Add the persistence model and migration**

```python
class KukuGroupSetting(Base):
    __tablename__ = 'kuku_group_settings'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True, unique=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    platform = sqlalchemy.Column(sqlalchemy.String(32), nullable=False)
    group_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    persona_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    silence_minutes = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=30)
    quiet_hours = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default={})
    cooldown_minutes = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=10)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
```

```python
required_database_version = 25
```

- [ ] **Step 4: Implement the minimal KUKU service methods**

```python
class KukuService:
    async def upsert_group_settings(self, payload: dict) -> dict:
        # validate bot exists and adapter is discord for MVP
        # insert or update by (bot_uuid, platform, group_id)
        ...
```

- [ ] **Step 5: Run the focused test again**

Run: `uv run pytest tests/unit_tests/kuku/test_kuku_service.py::test_upsert_group_settings_persists_persona_and_threshold -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/langbot/pkg/entity/persistence/kuku.py src/langbot/pkg/persistence/migrations/dbm025_kuku_group_settings.py src/langbot/pkg/entity/persistence/__init__.py src/langbot/pkg/utils/constants.py src/langbot/pkg/api/http/service/kuku.py tests/unit_tests/kuku/test_kuku_service.py
git commit -m "feat(kuku): add group settings persistence"
```

## Task 2: Expose KUKU setup and read APIs in LangBot core

**Files:**
- Create: `src/langbot/pkg/api/http/service/kuku.py`
- Create: `src/langbot/pkg/api/http/controller/groups/kuku.py`
- Modify: `src/langbot/pkg/core/app.py`
- Modify: `src/langbot/pkg/core/stages/build_app.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/__init__.py`
- Test: `tests/unit_tests/kuku/test_kuku_service.py`

- [ ] **Step 1: Write the failing API/service tests**

```python
async def test_list_personas_returns_fixed_mvp_personas(kuku_service):
    personas = await kuku_service.list_personas()
    assert [persona['id'] for persona in personas] == ['kuku-sunny']

async def test_get_group_settings_returns_none_for_unconfigured_group(kuku_service):
    result = await kuku_service.get_group_settings('bot-1', 'discord', 'missing')
    assert result is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit_tests/kuku/test_kuku_service.py -v`
Expected: FAIL because the new service methods and router are missing.

- [ ] **Step 3: Implement the service and router**

```python
@group.group_class('kuku', '/api/v1/kuku')
class KukuRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/personas', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _personas():
            return self.success(data={'personas': await self.ap.kuku_service.list_personas()})

        @self.route('/groups/<bot_uuid>/<platform>/<group_id>', methods=['GET', 'PUT'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _group(bot_uuid: str, platform: str, group_id: str):
            ...
```

- [ ] **Step 4: Register the service during app build**

```python
kuku_service_inst = kuku_service.KukuService(ap)
ap.kuku_service = kuku_service_inst
```

- [ ] **Step 5: Run the service tests**

Run: `uv run pytest tests/unit_tests/kuku/test_kuku_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/langbot/pkg/api/http/service/kuku.py src/langbot/pkg/api/http/controller/groups/kuku.py src/langbot/pkg/core/app.py src/langbot/pkg/core/stages/build_app.py src/langbot/pkg/api/http/controller/groups/__init__.py tests/unit_tests/kuku/test_kuku_service.py
git commit -m "feat(kuku): add setup service and api"
```

## Task 3: Add the Discord host bridge KUKU needs

**Files:**
- Modify: `src/langbot/pkg/platform/sources/discord.py`
- Modify: `src/langbot/pkg/platform/botmgr.py`
- Test: `tests/unit_tests/kuku/test_discord_runtime_bridge.py`

- [ ] **Step 1: Write the failing bridge tests**

```python
async def test_fetch_recent_group_messages_returns_latest_messages(discord_adapter):
    messages = await discord_adapter.fetch_recent_group_messages('123', limit=20)
    assert len(messages) == 2
    assert messages[0]['content'] == 'latest'

async def test_send_group_text_message_uses_existing_adapter_send_path(runtime_bot):
    await runtime_bot.adapter.send_plain_text_to_group('123', 'hello from kuku')
```

- [ ] **Step 2: Run the bridge tests to confirm failure**

Run: `uv run pytest tests/unit_tests/kuku/test_discord_runtime_bridge.py -v`
Expected: FAIL because the adapter does not yet expose KUKU-friendly helper methods.

- [ ] **Step 3: Add minimal Discord helper methods**

```python
class DiscordMessagePlatformAdapter(...):
    async def fetch_recent_group_messages(self, group_id: str, limit: int = 20) -> list[dict]:
        channel = self.bot.get_channel(int(group_id))
        ...

    async def send_plain_text_to_group(self, group_id: str, content: str) -> None:
        await self.send_message(
            'group',
            str(group_id),
            platform_message.MessageChain([platform_message.Plain(text=content)]),
        )
```

- [ ] **Step 4: Expose a narrow runtime lookup helper if needed**

```python
class PlatformManager:
    async def get_bot_adapter(self, bot_uuid: str):
        runtime_bot = await self.get_bot_by_uuid(bot_uuid)
        return runtime_bot.adapter if runtime_bot else None
```

- [ ] **Step 5: Run the bridge tests**

Run: `uv run pytest tests/unit_tests/kuku/test_discord_runtime_bridge.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/langbot/pkg/platform/sources/discord.py src/langbot/pkg/platform/botmgr.py tests/unit_tests/kuku/test_discord_runtime_bridge.py
git commit -m "feat(kuku): add discord runtime bridge helpers"
```

## Task 4: Create the KUKU plugin package skeleton and fixed persona config

**Files:**
- Create: `plugins/kuku/pyproject.toml`
- Create: `plugins/kuku/manifest.yaml`
- Create: `plugins/kuku/README.md`
- Create: `plugins/kuku/src/langbot_kuku_plugin/__init__.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/plugin.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/config.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/personas.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/models.py`
- Test: `tests/unit_tests/kuku/test_prompt_builder.py`

- [ ] **Step 1: Write the failing persona/config test**

```python
def test_fixed_mvp_persona_is_exposed():
    from langbot_kuku_plugin.personas import MVP_PERSONAS

    assert list(MVP_PERSONAS) == ['kuku-sunny']
    assert MVP_PERSONAS['kuku-sunny'].silence_trigger_style == 'question'
```

- [ ] **Step 2: Run the test to verify failure**

Run: `uv run pytest tests/unit_tests/kuku/test_prompt_builder.py::test_fixed_mvp_persona_is_exposed -v`
Expected: FAIL because the plugin package does not exist yet.

- [ ] **Step 3: Add the plugin manifest and typed config/persona models**

```yaml
apiVersion: v1
kind: Plugin
metadata:
  author: langbot
  name: kuku
  label:
    en_US: KUKU
spec:
  components:
    - kind: EventListener
      path: langbot_kuku_plugin.components.event_listener:KukuEventListener
    - kind: Command
      path: langbot_kuku_plugin.components.command:KukuSetupCommand
```

```python
MVP_PERSONAS = {
    'kuku-sunny': KukuPersona(
        id='kuku-sunny',
        name='KUKU',
        tags=['cheerful', 'energetic'],
        tagline='A bright group member who restarts quiet chats naturally.',
        system_prompt='You are KUKU...',
        silence_trigger_style='question',
    )
}
```

- [ ] **Step 4: Run the focused plugin test**

Run: `uv run pytest tests/unit_tests/kuku/test_prompt_builder.py::test_fixed_mvp_persona_is_exposed -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/kuku tests/unit_tests/kuku/test_prompt_builder.py
git commit -m "feat(kuku): scaffold plugin package"
```

## Task 5: Implement silence detection, memory ingestion, and prompt construction in the plugin

**Files:**
- Create: `plugins/kuku/src/langbot_kuku_plugin/services/silence.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/services/memory.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/services/profile.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/services/responder.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/services/runtime.py`
- Test: `tests/unit_tests/kuku/test_silence_scheduler.py`
- Test: `tests/unit_tests/kuku/test_prompt_builder.py`

- [ ] **Step 1: Write the failing scheduler and prompt tests**

```python
async def test_silence_detector_respects_threshold_and_cooldown():
    detector = SilenceDetector(now_fn=fake_now)
    detector.record_message('group-1')
    fake_now.advance(minutes=31)
    assert detector.should_fire('group-1') is True

def test_prompt_builder_injects_memories_for_active_users():
    prompt = build_system_prompt(persona, [alice], {'alice': ['likes anime']})
    assert 'likes anime' in prompt
    assert 'You are KUKU' in prompt
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `uv run pytest tests/unit_tests/kuku/test_silence_scheduler.py tests/unit_tests/kuku/test_prompt_builder.py -v`
Expected: FAIL because the runtime services do not exist.

- [ ] **Step 3: Implement minimal runtime services**

```python
class SilenceDetector:
    def should_fire(self, group_key: str) -> bool:
        # threshold + quiet hours + cooldown + jitter window
        ...

class MemoryManager:
    def ingest(self, user_id: str, message: str, group_id: str) -> None:
        self.memory.add(message, user_id=user_id, metadata={'group_id': group_id})

class KukuResponder:
    async def generate_opener(...):
        # persona + recent context + recalled memories -> LLM
        ...
```

- [ ] **Step 4: Run the unit tests**

Run: `uv run pytest tests/unit_tests/kuku/test_silence_scheduler.py tests/unit_tests/kuku/test_prompt_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/kuku/src/langbot_kuku_plugin/services tests/unit_tests/kuku/test_silence_scheduler.py tests/unit_tests/kuku/test_prompt_builder.py
git commit -m "feat(kuku): add runtime services"
```

## Task 6: Wire plugin event handling for proactive and reactive KUKU behavior

**Files:**
- Create: `plugins/kuku/src/langbot_kuku_plugin/components/event_listener.py`
- Create: `plugins/kuku/src/langbot_kuku_plugin/components/command.py`
- Modify: `plugins/kuku/src/langbot_kuku_plugin/plugin.py`
- Modify: `plugins/kuku/src/langbot_kuku_plugin/services/runtime.py`
- Modify: `src/langbot/templates/config.yaml`
- Modify: `docs/kuku-design.md`
- Test: `tests/unit_tests/kuku/test_discord_runtime_bridge.py`
- Test: `tests/unit_tests/kuku/test_silence_scheduler.py`

- [ ] **Step 1: Write the failing runtime behavior test**

```python
async def test_group_message_ingests_memory_and_resets_timer(kuku_runtime, group_message):
    await kuku_runtime.on_group_message(group_message)
    assert kuku_runtime.silence_detector.last_message_time['discord:123'] is not None
    assert kuku_runtime.memory_manager.ingested == [('user-1', 'hello', '123')]
```

- [ ] **Step 2: Run the runtime test to verify failure**

Run: `uv run pytest tests/unit_tests/kuku/test_discord_runtime_bridge.py tests/unit_tests/kuku/test_silence_scheduler.py -v`
Expected: FAIL because the event listener and runtime orchestration are not implemented.

- [ ] **Step 3: Implement the event listener and setup command**

```python
class KukuEventListener(...):
    async def on_group_message(self, event):
        await self.runtime.handle_group_message(event)

class KukuSetupCommand(...):
    async def execute(self, context):
        # MVP: reply with setup guidance and current persona/config
        ...
```

- [ ] **Step 4: Add plugin configuration defaults**

```yaml
plugin:
  kuku:
    mem0:
      provider: local
    scheduler:
      tick_seconds: 60
      jitter_seconds: 120
```

- [ ] **Step 5: Run the KUKU test slice**

Run: `uv run pytest tests/unit_tests/kuku -v`
Expected: PASS

- [ ] **Step 6: Run lint on touched Python files**

Run: `uv run ruff check src/langbot/pkg/api/http/service/kuku.py src/langbot/pkg/api/http/controller/groups/kuku.py src/langbot/pkg/platform/sources/discord.py src/langbot/pkg/platform/botmgr.py src/langbot/pkg/entity/persistence/kuku.py plugins/kuku/src/langbot_kuku_plugin tests/unit_tests/kuku`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/kuku src/langbot/templates/config.yaml docs/kuku-design.md tests/unit_tests/kuku
git commit -m "feat(kuku): wire discord mvp runtime"
```

## Task 7: Verify the end-to-end local MVP path

**Files:**
- Modify: `plugins/kuku/README.md`
- Test: `tests/unit_tests/kuku/test_kuku_service.py`
- Test: `tests/unit_tests/kuku/test_discord_runtime_bridge.py`
- Test: `tests/unit_tests/kuku/test_silence_scheduler.py`
- Test: `tests/unit_tests/kuku/test_prompt_builder.py`

- [ ] **Step 1: Document the local install/run flow**

```md
1. `uv sync --dev`
2. Install the local KUKU plugin package into the plugin runtime.
3. Create a Discord bot using the existing bots API/UI.
4. Configure KUKU for a Discord channel via `/api/v1/kuku/...` or the frontend follow-up.
```

- [ ] **Step 2: Run the full KUKU unit suite**

Run: `uv run pytest tests/unit_tests/kuku -v`
Expected: PASS

- [ ] **Step 3: Run the existing plugin regression tests**

Run: `uv run pytest tests/unit_tests/plugin -v`
Expected: PASS

- [ ] **Step 4: Run a broader regression slice**

Run: `uv run pytest tests/unit_tests/config tests/unit_tests/pipeline tests/unit_tests/storage -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/kuku/README.md
git commit -m "docs(kuku): add local mvp verification guide"
```

## Notes

- Discord-only is the MVP boundary. Reject non-Discord KUKU setup requests in `KukuService` until Feishu is implemented.
- Keep the persona list fixed to one entry in the first iteration even though the API returns a list.
- The plugin should call LangBot core APIs for group settings reads rather than duplicating persistence access if the runtime boundary makes direct DB access awkward.
- Mem0 must not default to in-memory storage in production code paths. Use explicit config validation and fail loudly when persistent backing services are missing.
- If plugin packaging in `plugins/kuku/` proves incompatible with the runtime installer, move the package to its own repository without changing the service and API boundaries defined above.

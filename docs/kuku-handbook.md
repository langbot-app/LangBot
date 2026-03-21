# KUKU Handbook

## What These Changes Do

This branch adds the first KUKU backend slice for LangBot.

The current implementation covers two things:

1. **Persisted KUKU group settings**
   - Adds a `kuku_group_settings` table and migration `25`
   - Stores the Discord group scope, persona, silence threshold, cooldown, quiet hours, and enabled flag

2. **Initial KUKU setup/read API surface**
   - `GET /api/v1/kuku/personas`
   - `GET /api/v1/kuku/groups/<bot_uuid>/<platform>/<group_id>`
   - `PUT /api/v1/kuku/groups/<bot_uuid>/<platform>/<group_id>`

The service layer currently enforces the MVP boundary:
- Discord only
- One fixed persona: `kuku-sunny`
- Validation for boolean, integer, and quiet-hours payloads before settings are persisted

What is **not** implemented yet:
- silence detection
- proactive KUKU messaging
- plugin runtime behavior
- Discord adapter runtime integration beyond storing and reading KUKU config

So at this point, the branch gives LangBot a place to store KUKU configuration and an API to manage and read it back.

## Files Added or Updated

Core implementation:
- `src/langbot/pkg/entity/persistence/kuku.py`
- `src/langbot/pkg/persistence/migrations/dbm025_kuku_group_settings.py`
- `src/langbot/pkg/api/http/service/kuku.py`
- `src/langbot/pkg/api/http/controller/groups/kuku.py`
- `src/langbot/pkg/core/app.py`
- `src/langbot/pkg/core/stages/build_app.py`
- `src/langbot/pkg/utils/constants.py`

Tests:
- `tests/unit_tests/kuku/test_kuku_service.py`

Reference docs:
- `docs/kuku-design.md`
- `docs/superpowers/plans/2026-03-20-kuku-discord-mvp.md`

## How To Test The Changes

### Automated Checks

Run the focused KUKU service test suite:

```bash
uv run pytest tests/unit_tests/kuku/test_kuku_service.py -v
```

This covers:
- persona listing
- reading saved group settings
- insert and upsert behavior
- Discord-only validation
- boolean/int/quiet-hours validation
- PostgreSQL upsert SQL generation
- migration table/index/constraint creation

Run a syntax check for the changed Python files:

```bash
uv run python -m py_compile \
  src/langbot/pkg/api/http/service/kuku.py \
  src/langbot/pkg/api/http/controller/groups/kuku.py \
  src/langbot/pkg/core/app.py \
  src/langbot/pkg/core/stages/build_app.py \
  src/langbot/pkg/entity/persistence/kuku.py \
  src/langbot/pkg/persistence/migrations/dbm025_kuku_group_settings.py
```

### Manual API Checks

1. Start LangBot normally so database migration `25` applies.

2. Use an existing Discord bot record or create one through the normal bot management flow.

3. Fetch the fixed MVP persona list:

```bash
curl http://127.0.0.1:5300/api/v1/kuku/personas \
  -H "Authorization: Bearer <token>"
```

4. Save KUKU settings for a Discord group:

```bash
curl -X PUT http://127.0.0.1:5300/api/v1/kuku/groups/<bot_uuid>/discord/<group_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "kuku-sunny",
    "silence_minutes": 30,
    "cooldown_minutes": 10,
    "quiet_hours": {
      "start": "00:00",
      "end": "08:00",
      "timezone": "UTC"
    },
    "enabled": true
  }'
```

5. Read those settings back:

```bash
curl http://127.0.0.1:5300/api/v1/kuku/groups/<bot_uuid>/discord/<group_id> \
  -H "Authorization: Bearer <token>"
```

Expected result:
- the saved values are returned
- invalid platforms are rejected
- malformed booleans, integers, or quiet-hours payloads are rejected before persistence

## Current Scope

This handbook describes the branch state after **Task 2** of the implementation plan:
- Task 1: persistence and validation
- Task 2: setup/read API surface

Later KUKU runtime behavior should extend this handbook rather than replacing it.

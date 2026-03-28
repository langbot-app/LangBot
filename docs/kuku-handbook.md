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

## Why This Exists In The Current PR

This PR is intentionally the setup-and-persistence slice, not the full KUKU runtime.

We are doing this first because the later runtime work needs a stable contract for:

- which Discord bot and group KUKU is attached to
- whether KUKU is enabled for that group
- which persona and operational thresholds the future silence detector should use

Without this persistence layer first, later work such as silence detection and proactive messaging would either hardcode configuration or keep it only in memory, which would make the MVP harder to test and demo safely.

## What Is Still Needed After This PR

This branch does not yet make KUKU speak in Discord. The main missing pieces are:

- a runtime loop that watches Discord group activity and evaluates silence windows
- the logic that turns saved group settings into actual proactive KUKU messages
- prompt assembly and LLM invocation for proactive and reactive KUKU replies
- end-to-end integration from Discord events into the KUKU runtime path
- frontend or operator UX beyond calling the setup/read APIs directly

For review purposes, that means this PR should be evaluated as backend groundwork, not as a feature-complete KUKU MVP.

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

## Demo Today

For a demo today, position this branch as "KUKU setup is now persisted and retrievable inside LangBot".

Recommended flow:

1. Start LangBot and confirm migration `25` has been applied.
2. Show that a Discord bot already exists in LangBot and copy its `bot_uuid`.
3. Call `GET /api/v1/kuku/personas` to show the MVP persona catalog.
4. Call the `PUT /api/v1/kuku/groups/<bot_uuid>/discord/<group_id>` endpoint with a real or sample Discord group ID.
5. Call the matching `GET` endpoint and show that the same values come back from persistence.
6. Trigger one invalid request, such as `platform=slack` or `enabled=\"maybe\"`, to show the guardrails.
7. Close by stating that the runtime behavior is the next slice and this PR is the foundation that makes that runtime configurable.

If you want the smoothest demo, prepare these ahead of time:

- one valid auth token or API key
- one known Discord bot UUID
- one sample Discord group ID
- one saved `curl` command for the success case
- one saved `curl` command for the invalid-input case

## Current Scope

This handbook describes the branch state after **Task 2** of the implementation plan:
- Task 1: persistence and validation
- Task 2: setup/read API surface

Later KUKU runtime behavior should extend this handbook rather than replacing it.

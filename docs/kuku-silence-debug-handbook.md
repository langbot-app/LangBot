# KUKU — Silence detector debug handbook

Use this when you want **visible proof** that the KUKU background loop is running and when you need a **sub-minute** silence threshold (for example **30 seconds**) without waiting one full minute.

For full end-to-end Discord setup (bot, pipeline, API auth), see [kuku-discord-runtime-runbook.md](./kuku-discord-runtime-runbook.md) and [kuku-bootstrap-runbook.md](./kuku-bootstrap-runbook.md).

---

## 1. What you will see when debug mode is on

With debug enabled, LangBot logs **one line per detector tick** at **INFO** for logger `langbot.kuku`:

```text
KUKU silence detector tick #12 (interval=10.0s)
```

The number (`#12`, …) increases every tick so you can confirm the loop is alive. Ticks run only while `uv run main.py` (or your production process) stays up.

---

## 2. Environment variables

Set these **before** starting the backend in the same shell (or export them in your process manager).

| Variable | Effect |
|----------|--------|
| `KUKU_SILENCE_DEBUG=1` | Log each silence-detector tick at INFO (`1`, `true`, or `yes`, case-insensitive). |
| `KUKU_SILENCE_TICK_INTERVAL_SEC=10` | Sleep between ticks (seconds). Clamped to **5–300**; default **20** if unset or invalid. |

Example:

```bash
export KUKU_SILENCE_DEBUG=1
export KUKU_SILENCE_TICK_INTERVAL_SEC=10
uv run main.py
```

**Production:** leave `KUKU_SILENCE_DEBUG` unset so logs stay quiet. The default tick interval remains 20 seconds unless you override it.

---

## 3. Sub-minute silence: `silence_seconds`

Group settings support an optional **`silence_seconds`** field. When it is a **positive integer**, the runtime uses it as the **required quiet period** (in seconds) after the last **human** message before KUKU may send a proactive opener. When it is **omitted** or **null**, behavior falls back to **`silence_minutes`** (same as before).

- Upper bound: **86400** (24 hours), enforced by the API.
- **`silence_seconds`: 0** or omitting the field clears the override (stored as SQL `NULL`); threshold uses `silence_minutes` only.

Database note: schema version **26** adds the `silence_seconds` column. Run the backend once so migrations apply, or run your usual migration path.

### Example PUT (30-second silence, minimal cooldown)

Use your real `KUKU_API_BASE_URL`, `KUKU_API_KEY`, `KUKU_BOT_UUID`, and `KUKU_GROUP_ID` (Discord **channel** snowflake).

```bash
curl -s -X PUT "${KUKU_API_BASE_URL}/api/v1/kuku/groups/${KUKU_BOT_UUID}/discord/${KUKU_GROUP_ID}" \
  -H "Authorization: Bearer ${KUKU_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "silence_minutes": 30,
    "silence_seconds": 30,
    "cooldown_minutes": 0,
    "enabled": true,
    "quiet_hours": {}
  }'
```

Then:

1. Post **one** message in that channel as a **human** user.
2. Wait **at least 30 seconds** without posting.
3. Within about one tick interval (e.g. 10 s with the env override), KUKU should post an opener.

`cooldown_minutes: 0` makes it easier to re-test quickly; for realistic behavior, use a positive cooldown.

---

## 4. Quick checks if nothing fires

| Check | Detail |
|--------|--------|
| Logs show ticks? | If not, confirm `KUKU_SILENCE_DEBUG=1` and log level allows INFO for `langbot.kuku`. |
| Human message after enable? | In-memory **last activity** is updated from **human** messages only, after KUKU is enabled for that channel. |
| `group_id` | Must match the **text channel** id you are testing in Discord. |
| Quiet hours | Empty `quiet_hours: {}` disables the window. |
| LLM / bot | Opener still requires a working `local-agent` pipeline and Discord `send_message`; errors appear under `langbot.kuku`. |

---

## 5. Returning to normal thresholds

1. Stop using debug env vars (or unset them) and restart LangBot.
2. PUT settings **without** `silence_seconds`, or set **`silence_seconds` to `null`** in JSON if your client sends explicit nulls, so the stored value is cleared and **`silence_minutes`** alone defines the threshold.

---

## Related code

- Background loop and thresholds: `src/langbot/pkg/kuku/runtime.py`
- Persistence and validation: `src/langbot/pkg/api/http/service/kuku.py`
- Discord activity hook: `src/langbot/pkg/platform/botmgr.py`

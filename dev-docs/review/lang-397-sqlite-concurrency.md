# SQLite concurrency investigation

## Scope and environment

LANG-397 targets Core 4.11.6. The reproduction uses v4.11.5
(`d6af39a83`) and the implementation is based on master `9a65a9c5b`.
The SQLite manager, resource URL refresh, run ledger and tenant SQL guard
are identical between those two revisions.

Validation runs on Linux with Python 3.12.13, SQLite 3.50.4,
SQLAlchemy 2.0.46 and the locked SDK 0.7.23. All application tests use
`SPACE__DISABLE_TELEMETRY=true`, temporary data directories and independent
ports. The E2E uses the real Core, SDK Plugin Runtime and official LocalAgent;
the model and tool results are deterministic test resources, with no external
provider calls.

## Database locking

`refresh_images` starts `BEGIN IMMEDIATE` before reading the URL catalog.
In v4.11.5 this transaction remains open across OneBot `get_version_info`
and image renewal calls such as `get_msg`. SQLite has one database writer,
so unrelated Agent event inserts, status updates and execution lease writes
can exhaust the default five-second busy timeout while the upstream call waits.
WAL is already enabled; enabling it again does not address this writer conflict.

The fix releases the SQLite transaction before upstream I/O and uses an
engine-local lock to retain same-engine refresh deduplication. Updates use a
short immediate transaction and compare the current catalog identity, URL and
last-check timestamp with the saved snapshot. Another engine's newer result or
canonical redirect wins over a stale upstream result. PostgreSQL retains its
existing row-lock path. Plain-text payloads do not wait for the refresh lock,
and cancellation releases it.

Every SQLite connection also sets a bounded 30-second busy timeout for bursts
of concurrent short writes, including connections recreated after pool
disposal. This does not retry arbitrary transactions or hide I/O failures.

### Reproduction and regression evidence

- The pre-fix storage reproduction fails in both upstream-wait locations with
  `sqlite3.OperationalError: database is locked`, including
  `INSERT INTO agent_run_event` and `UPDATE agent_run`.
- The same E2E against v4.11.5 fails with `database is locked` while creating
  concurrent Agent runs. With the fix, four independent conversations finish,
  execute four authorized tools through Host actions, and persist four
  `tool.call.completed` events and four completed runs while image refresh
  is still waiting.
- Both 16-conversation storage stress cases pass. Each case persists 192 run
  events and completes all 16 runs while either version identification or
  image renewal remains blocked.
- Regression coverage includes same-engine refresh deduplication, cross-engine
  stale results and canonical redirects, cancellation, pooled connection
  settings and the existing tenant SQL validation boundaries.
- The combined resource URL, run ledger, tenant UOW, plugin action, SQLite
  startup/concurrency/reclamation suite passes **303 tests**, with **18
  PostgreSQL cases skipped**. This broader suite uses an isolated tmpfs
  temporary directory; the reproduction, 16-conversation stress and real
  LocalAgent E2E use disk-backed temporary databases.
- Ruff checks and the Core wheel build pass. No SDK or plugin version changes
  are required.

The reproduced path establishes a reachable Core bug, not attribution of every
historical lock-error record to that path.

## Unable to open database file

Isolated Linux probes produce the same `SQLITE_CANTOPEN` (14) and
`unable to open database file` for each of:

- A missing database parent directory.
- A database directory without access permission.
- Process-local file descriptor exhaustion, using a reduced descriptor limit
  only in the diagnostic subprocess.

Changing the working directory after SQLAlchemy engine creation, disposing its
pool and selecting `workspaces` again succeeds: the existing SQLite dialect
connection arguments retain the resolved path. This rules out that particular
working-directory hypothesis, not startup with an incorrect path.

The truncated telemetry does not distinguish the three observed environment
failures or establish a Core descriptor leak. No automatic directory creation,
permission changes or database replacement is introduced.

## Disk I/O errors

The available error text does not identify a failing SQLite operation or its
extended error code. A disk, filesystem or mount problem is plausible, but the
two affected installations cannot be diagnosed from that string alone. No
claim is made that all 33 records are environmental, and no retry or error
suppression is added.

## Tenant upserts

SQLAlchemy 2.0 stores `OnConflictDoUpdate.update_values_to_set` as a list of
key/value tuples; SQLAlchemy 2.1 uses a mapping. Iterating the mapping directly
feeds keys into the tuple-shape check, causing `unknown ON CONFLICT update shape`
for both SQLite and PostgreSQL. The `SET_BINARY_STORAGE` Host action uses this
upsert for a new key, while an existing key uses an ordinary update.

The guard converts mappings to `.items()` before iterating. Pair-shape,
identifier and embedded-expression validation remain unchanged. The supported
dependency range is `sqlalchemy[asyncio]>=2.0.40,<2.2`; the lock retains its
SQLAlchemy 2.0.46 pin. CI explicitly installs both 2.0.x and 2.1.x and uses
`uv run --no-sync` so the lock cannot conceal compatibility failures.

Against master `c17b065bf`, the real Host action through `PersistenceManager`
and `TenantUnitOfWork` reproduces the new-key failure with SQLAlchemy 2.1.8 and
succeeds with 2.0.49. Regression coverage verifies the committed bytes and
Workspace/key identity for both a new key and its subsequent update, plus
SQLite/PostgreSQL statement validation and the tenant SQL rejection tests.
SQLAlchemy 2.0.49 and 2.1.8 each pass all 239 tenant UOW, failed-commit and
plugin-action regression cases on Linux/Python 3.12.13. Both environments use
isolated temporary SQLite databases and disable telemetry. The 2.0.49 run uses
SQLModel 0.0.31; the 2.1.8 run uses SQLModel 0.0.48. CI resolves SQLModel together
with SQLAlchemy and checks dependency consistency: the locked SQLModel 0.0.31
requires SQLAlchemy below 2.1, whereas 0.0.48 supports 2.1.

## Remaining evidence

For open/I/O failures, obtain the affected OS, SQLite extended error code,
directory/mount status and descriptor counts around failure. Redact credentials
and user payloads.

PostgreSQL-specific resource URL tests require `TEST_POSTGRES_URL` and are
skipped in this environment. The incremental reclamation tests have a
100-millisecond round budget; the four adaptive-batch cases fail on this host
because only one batch fits, including against unmodified v4.11.5. Their code
and timing assertions are unchanged; all four pass in the tmpfs regression run.

# Cross-component acceptance

Run the paths affected by the change before recommending merge. A passing PR check covers only its selected contracts. Daily coverage is additional evidence; it does not replace acceptance of a changed backend. All commands below start at the repository root on the approved Linux development host. Follow the execution-host restrictions in the active workspace instructions; when local macOS execution is restricted, use the designated remote host and report unavailable verification instead of falling back to Mac.

## P0 pull-request acceptance

`core-smoke.yml` calls the reusable `p0-acceptance.yml` before its existing required
`Core smoke (60s)` job. Backend/SDK/dependency/workflow changes select all P0 paths;
test-only changes select their affected boundary. Documentation and WebUI-only
changes do not select backend acceptance. Selected jobs must succeed; a missing
environment, failed job, cancellation or skipped required case blocks the existing
required smoke status. No online branch-rule change is needed after this workflow
is merged.

- `persistence-acceptance.yml` is shared with Daily Endurance. It runs real
  Core/Plugin Runtime/Box file delivery and PG/MinIO/two-Core recovery.
- `p0_permissions` runs real Core/Runtime/SDK installation, confirmation, upgrade,
  uninstall/reinstall, in-flight revocation and HTTP/MCP key revocation. It also
  checks independent database readback across Workspaces.
- `p0_image` uses the production Dockerfile's candidate image and the published
  `rockchin/langbot:v4.11.7` baseline. It seeds old Skill versions and images,
  upgrades, removes legacy source paths, replaces the Core and Runtime containers and checks
  retained content and newly installed plugin grants. A separate empty volume
  checks generated persistence/network defaults. Containers publish loopback-only
  HTTP ports. Verification does not recreate missing data.

For Linux image acceptance, set `LANGBOT_IMAGE_CANDIDATE` and
`LANGBOT_IMAGE_PREVIOUS`, then run:

```sh
uv run --no-sync pytest tests/e2e/test_image_upgrade.py --required-suite p0_image -q -rs
LANGBOT_PERMISSION_E2E=1 uv run --no-sync pytest \
  tests/integration/api/test_plugin_permission_lifecycle.py \
  tests/integration/api/test_application_foundation.py --required-suite p0_permissions -q -rs
```

Image tests accept `LANGBOT_TEST_DOCKER_COMMAND` for the approved Docker CLI
invocation (default `docker`). Core and Runtime run on a task-owned Docker network,
following the production Compose topology. Their logs are retained under
`.qa/image-upgrade`. Permission process evidence is retained
under `.qa/permissions`. Private seed state and authentication material are not
uploaded as CI evidence. These paths do not establish real-model understanding,
non-host Box backend behavior or compatibility with every historical release.

## Shared SDK, API and Runtime changes

Standard Core `uv sync` installs the SDK from this checkout's `sdk/` through the root local source declaration. No overlay or SDK publication is needed to test coordinated changes:

```sh
uv sync --dev --frozen
uv run --no-sync pytest tests/integration/plugin --required-suite sdk_core -q -rs
```

This executes Core/SDK action routing, file envelopes and cancellation contracts. It uses real SDK handlers with local transports and explicit service doubles; it does not establish full-process file delivery. Run the affected SDK tests under `sdk/` as well.

The Runner, LocalAgent and KnowledgeEngine workflows trigger on Core and SDK changes. They retain their released-SDK paths and then test the candidate SDK against existing official plugin consumers. Runner RPC tests check each plugin's declared requirements in its actual interpreter. Do not rewrite all plugin pins to satisfy a candidate. A plugin outside the candidate's declared support range needs an explicit compatibility decision, not a forced upgrade. Follow each workflow's isolated dependency setup when reproducing these tests.

## Choose the real acceptance path

| Changed behavior | Required developer acceptance | Environment |
| --- | --- | --- |
| File import/export, Runtime envelopes, persistent grants, reply delivery | `network_plugin` below | Full Core + Plugin Runtime + installed test Runner + Box on loopback; host is the account-free baseline |
| Skill publication, content aliases, media, cache or database schema | `skill_persistence` below | Disposable PostgreSQL + MinIO and two real Core processes; includes SQLite, PostgreSQL and named-S3 replicas, CAS, retained versions, migration/RLS, restart and deleted-cache recovery |
| Network Skill execution, resource reads or draft registration | `skill_network` below | Two real Core processes with independent Plugin/Box Runtimes and no shared Skill/workspace roots; run pins across publication, registration, grants, restart and cancellation |
| Box backend execution, mounts, sessions or file transfer | Relevant `sdk/tests/box` and Core Box tests; repeat network delivery on the changed supported backend | Docker/Podman, nsjail or E2B as applicable; host success does not establish another backend's behavior |

```sh
LANGBOT_NETWORK_PLUGIN_E2E=1 LANGBOT_CORE_NETWORK_BACKEND=host \
  uv run --no-sync pytest tests/e2e/test_network_file_plugin_runtime.py \
  --required-suite network_plugin -q -rs --junitxml=network-plugin.xml

# Both PostgreSQL URLs must point to task-owned disposable databases.
# The two-Core database must be fresh; the integration database needs schema/role creation.
export LANGBOT_PERSISTENCE_POSTGRES_URL='postgresql+asyncpg://postgres@127.0.0.1:5432/langbot_test'
export LANGBOT_PERSISTENCE_CORE_POSTGRES_URL='postgresql+asyncpg://postgres@127.0.0.1:5432/langbot_core'
export LANGBOT_PERSISTENCE_MINIO_ENDPOINT='http://127.0.0.1:9000'
# Supply ACCESS_KEY/SECRET_KEY through the environment for the disposable MinIO.
export LANGBOT_PERSISTENCE_CORE_E2E=1
uv run --no-sync pytest tests/integration/skill/test_persistent_skill_replicas.py \
  tests/integration/skill/test_legacy_skill_migration.py tests/integration/storage/test_legacy_storage_migration.py \
  tests/integration/persistence/test_skill_content_postgres.py tests/e2e/test_skill_persistence_replicas.py \
  --required-suite skill_persistence -q -rs --junitxml=skill-persistence.xml

# Use another fresh task-owned database for this independent pair of Core processes.
export LANGBOT_PERSISTENCE_CORE_POSTGRES_URL='postgresql+asyncpg://postgres@127.0.0.1:5432/langbot_skill_network'
LANGBOT_SKILL_NETWORK_E2E=1 uv run --no-sync pytest tests/e2e/test_skill_network_runtime.py \
  --required-suite skill_network -q -rs --junitxml=skill-network.xml
```

`tests/utils/required_suites.py` enforces the selected behavior obligations and rejects missing cases, skips, xfails and xpasses. Do not use `-k`, `-m` or `--deselect` to turn partial execution into acceptance. The explicit paths above keep collection narrow; the suite still fails if a required contract is missing.

For an actual legacy-Core upgrade, also run `tests/e2e/test_skill_legacy_upgrade.py`
with `LANGBOT_UPGRADE_OLD_SOURCE`, `LANGBOT_UPGRADE_OLD_PYTHON` (using its own old
SDK), and `LANGBOT_UPGRADE_POSTGRES_URL`. Supply a second fresh database through
`LANGBOT_FRESH_POSTGRES_URL` to check generated-template defaults. This path runs
old Core HTTP writes, migration, source-volume removal, restart and a second
Core. Box is disabled here; Runtime acceptance remains the separate network suite.
The normal daily suite does not provision historical Core interpreters.

`daily-endurance.yml` calls the same reusable persistence acceptance on GitHub-hosted Linux, with the local SDK and temporary loopback PostgreSQL/MinIO services. The other endurance/API/provider jobs retain their existing scope.

For nsjail, use an already prepared host and its delegated `LANGBOT_NSJAIL_CGROUP_V1_PARENT`. For E2B, use explicitly authorized `E2B_API_KEY`, `E2B_API_URL`, `E2B_SANDBOX_URL` and optional `E2B_TEMPLATE`. Set `LANGBOT_CORE_NETWORK_BACKEND=nsjail` or `e2b` for the same network suite. Do not add credentials, change machine configuration, or expose private development machines as runners for public PR code. These backend runs remain developer acceptance until suitable dedicated infrastructure exists.

Record candidate SHA, SDK source/version, actual service/backend configuration without secrets, command and exit status, JUnit/log evidence, and unverified scope. Report environment failure separately from a product failure. Missing environment or skipped cases leave the relevant acceptance incomplete.

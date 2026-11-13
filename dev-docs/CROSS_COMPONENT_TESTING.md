# Cross-component acceptance

Run the paths affected by the change before recommending merge. A passing PR check covers only its selected contracts. Daily coverage is additional evidence; it does not replace acceptance of a changed backend. All commands below start at the repository root on the approved Linux development host. Follow the execution-host restrictions in the active workspace instructions; when local macOS execution is restricted, use the designated remote host and report unavailable verification instead of falling back to Mac.

## Shared SDK, API and Runtime changes

Keep the normal `uv sync --dev --frozen` tests against Core's published SDK pin. In a separate environment or after that run, install the candidate SDK and preserve it for every subsequent command:

```sh
uv sync --dev --frozen
uv pip install ./sdk
uv run --no-sync pytest tests/integration/plugin --required-suite sdk_core -q -rs
```

This executes Core/SDK action routing, file envelopes and cancellation contracts. It uses real SDK handlers with local transports and explicit service doubles; it does not establish full-process file delivery. Run the affected SDK tests under `sdk/` as well.

The Runner, LocalAgent and KnowledgeEngine workflows trigger on Core and SDK changes. They retain their released-SDK paths and then test the candidate SDK against existing official plugin consumers. Runner RPC tests check each plugin's declared requirements in its actual interpreter. Do not rewrite all plugin pins to satisfy a candidate. A plugin outside the candidate's declared support range needs an explicit compatibility decision, not a forced upgrade. Follow each workflow's isolated dependency setup when reproducing these tests.

## Choose the real acceptance path

| Changed behavior | Required developer acceptance | Environment |
| --- | --- | --- |
| File import/export, Runtime envelopes, persistent grants, reply delivery | `network_plugin` below | Full Core + Plugin Runtime + installed test Runner + Box on loopback; host is the account-free baseline |
| Skill publication, content aliases, media, cache or database schema | `skill_persistence` below | Disposable PostgreSQL + MinIO and two real Core processes; includes SQLite, PostgreSQL and named-S3 replicas, CAS, retained versions, migration/RLS, restart and deleted-cache recovery |
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
  tests/integration/persistence/test_skill_content_postgres.py tests/e2e/test_skill_persistence_replicas.py \
  --required-suite skill_persistence -q -rs --junitxml=skill-persistence.xml
```

`tests/utils/required_suites.py` enforces the selected behavior obligations and rejects missing cases, skips, xfails and xpasses. Do not use `-k`, `-m` or `--deselect` to turn partial execution into acceptance. The explicit paths above keep collection narrow; the suite still fails if a required contract is missing.

The existing `daily-endurance.yml` runs both account-free suites on GitHub-hosted Linux, overlays the in-tree SDK, and creates temporary loopback PostgreSQL/MinIO services. The other endurance/API/provider jobs retain their existing scope. It neither adds a PR required check nor runs the heavyweight recovery suite on every PR.

For nsjail, use an already prepared host and its delegated `LANGBOT_NSJAIL_CGROUP_V1_PARENT`. For E2B, use explicitly authorized `E2B_API_KEY`, `E2B_API_URL`, `E2B_SANDBOX_URL` and optional `E2B_TEMPLATE`. Set `LANGBOT_CORE_NETWORK_BACKEND=nsjail` or `e2b` for the same network suite. Do not add credentials, change machine configuration, or expose private development machines as runners for public PR code. These backend runs remain developer acceptance until suitable dedicated infrastructure exists.

Record candidate SHA, SDK source/version, actual service/backend configuration without secrets, command and exit status, JUnit/log evidence, and unverified scope. Report environment failure separately from a product failure. Missing environment or skipped cases leave the relevant acceptance incomplete.

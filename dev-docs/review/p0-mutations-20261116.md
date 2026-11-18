# P0 mutation experiment, 2026-11-16

The selected fast tests missed two reproducible input boundaries: an exactly
allowed content size, and string permission values. They also did not call
`installation_context` directly. Added tests now reject changed installation
identity, stale revision/digest, disabled installations, lost grants and changed
execution context using real persisted SQLite rows.

This is a bounded experiment on three functions, not a repository mutation score
or an estimate of how many production bugs the tests catch. Product code was not
changed. The per-mutant diff, exit codes, survivor disposition and representative
confirmation results are in [the result data](p0-mutations-20261116.json).

## Results

Product baseline: `fef053f7f55e1776fd31d6c26ae2f63e96dba4d9`; bundled SDK
`langbot-plugin 0.7.25`; Linux/Python 3.12; `mutmut 3.8.1`. All execution used
isolated Linux copies, outside the development checkout. The generator produced
1,533 variants in the three source modules; the three function patterns selected
102 distinct variants. The other 1,431 were outside this experiment.

| Selected function | Initial killed / survived / not covered | After supplementation, each of two runs |
| --- | --- | --- |
| `ContentStore._validated_value` (20) | 12 / 8 / 0 | 13 killed, 7 survived |
| `require_permission` (9) | 7 / 2 / 0 | 8 killed, 1 survived |
| `installation_context` (73) | 0 / 0 / 73 | 66 killed, 7 survived |
| Total | 19 / 10 / 73 | 87 killed, 15 survived |

The unmodified-code baseline passed 58 tests before supplementation and 64 after.
The final 102 outcomes were identical across two fresh mutmut executions. No
compile/import/infrastructure error, timeout or uncovered variant was counted
as a kill. The initial 73 uncovered variants describe the selected fast test
files; the existing full-process permission suite calls this function in child
processes and is not traced by this mutmut run.

Three representative engine-generated changes were also applied individually
to another isolated copy and checked in separate pytest processes twice each:

- `>` to `>=` in the content size bound: original passed; mutant failed the
  exact-limit assertion once per run.
- Force enum conversion for a wire-format permission string: original passed;
  mutant failed the string permission test once per run.
- Change the stale revision/digest disjunction to a conjunction: original
  passed; mutant failed both independent stale-binding cases per run.

These are behavior failures rather than compilation failures. The remaining
kills include diagnostic changes already asserted by old tests; 87 kills do not
mean 87 distinct business defects.

## Remaining 15 variants

All 15 are classified `NO_NEW_TEST_JUSTIFIED` for the present call chain; this is
not a proof of equivalence under future callers or configuration changes.

| Function and mutmut suffix | Why no additional test was added |
| --- | --- |
| `_validated_value`: 5, 6, 7, 8 | Change size-error text. Read callers already enforce the bound before this helper; the cached Skill publication path uses its publication bound. |
| `_validated_value`: 18, 19 | Change digest-error prefix/case while preserving failure. Exact English wording is not a contract. |
| `installation_context`: 15, 16, 17, 27, 28, 29 | Change disabled/stale diagnostic prefix/case. Tests enforce denial, error code and a nonempty string message. |
| `_validated_value`: 4 | Replaces the helper's bound with its default. Public reads have already checked the requested bound; no valid-input counterexample was demonstrated through current callers. Revisit if callers change. |
| `require_permission`: 2 | Takes the string branch for `Permission`, a `StrEnum`; the downstream check normalizes again. Enum and wire-string authorization behavior remains the same. |
| `installation_context`: 31 | Uses the default operation catalog. The fallback constructs the same current static `ApplicationAPI` catalog. Revisit if production catalogs become configurable. |

## Reproduce the bounded run

Use a disposable Linux copy and `uv sync --dev --frozen`. Install the engine only
in that disposable environment with `uv pip install mutmut==3.8.1`; it is not a
new application dependency. Append this configuration to that copy's
`pyproject.toml`:

```toml
[tool.mutmut]
source_paths = ["src/"]
only_mutate = [
  "src/langbot/pkg/api/authz.py",
  "src/langbot/pkg/api/application/plugin_permissions.py",
  "src/langbot/pkg/storage/content.py",
]
pytest_add_cli_args_test_selection = [
  "tests/unit_tests/api/http/test_authz.py",
  "tests/unit_tests/api/test_plugin_permissions.py",
  "tests/unit_tests/api/test_installation_authority.py",
  "tests/unit_tests/storage/test_content_store.py",
]
pytest_add_cli_args = ["-q", "--tb=short"]
also_copy = ["pytest.ini", "sdk/", "res/"]
timeout_multiplier = 3.0
timeout_constant = 5.0
use_git_change_detection = false
```

```sh
uv run --no-sync pytest tests/unit_tests/api/http/test_authz.py \
  tests/unit_tests/api/test_plugin_permissions.py \
  tests/unit_tests/api/test_installation_authority.py \
  tests/unit_tests/storage/test_content_store.py -q
uv run --no-sync mutmut run '*require_permission*' '*installation_context*' \
  '*_validated_value*' --max-children 4
uv run --no-sync mutmut results --all true
```

For the initial result use the baseline source/tests and omit the new authority
test file. A repeated run must clear the selected exit-code cache or use a fresh
copy; reading cached results is not another execution. Keep original-code
baseline, per-mutant outcomes and pytest failures when evaluating a new change.

P0 process/image acceptance is separate from this fast mutation experiment.
Real model behavior, non-host Box backends, crash injection and every historical
upgrade version remain outside this change's demonstrated coverage.

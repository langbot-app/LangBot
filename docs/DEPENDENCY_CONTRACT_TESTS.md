# Provisioned dependency contracts

`.github/workflows/optional-contracts.yml` runs three isolated jobs for optional
product dependencies. Every job provisions its dependency and rejects missing,
skipped, failed, or errored required cases. These are tests of actual integration
boundaries; removing them or substituting fake external implementations would
lose coverage. No production credentials or external model accounts are needed.

The fixtures are deliberately pinned for reproducibility. They are not a promise
that the latest release of every external repository passes. Update pins only
after rerunning the relevant contracts. This workflow is separate from the
latest-LocalAgent Space-resolution work in PR #2632.

## Official plugin identity boundary

The source lock in `tests/fixtures/legacy_plugin_identity_sources.json` records
the official repository, immutable revision, and SHA-256 of every consumed file
(including plugin manifests). CI checks out that revision with read-only access
and no persisted Git credentials. Tests verify file digests before executing the
actual identity methods, their genuine configuration-error classes, and their
real `scoped_identity` dependency. Vendor HTTP clients are not constructed.

The original test expected bare upstream user IDs and extracted only one method
from a hard-coded sibling checkout. Supported current plugins intentionally
namespace IDs by Workspace or trusted installation, so merely provisioning that
old test produced false failures. The current fixture is:

- Official repository: `langbot-app/langbot-plugins`
- Revision: `7ad54b1a139d88113bc55128326800ed29779737`
- DifyAgent 0.2.3; N8nAgent, CozeAgent and TboxAgent 0.2.2
- All exceed Core's current migration minimums (0.1.10; TboxAgent 0.1.8)

The 19 Host provenance/resume tests retain their exact raw-identity assertions.
The consumer boundary adds dedicated/shared profiles to the former eight cases:
16 real-plugin cases verify the independently specified session/event/bot source,
current documented namespace, and rejection of missing trusted identity. Shared
cases use the real SDK `bind_invocation` and `InstallationBinding`. They are not
full plugin-installation, vendor API, or migration-admission tests.

The documented semantic change is in each pinned plugin's `SHARED_RUNTIME.md`,
for example [Dify's upstream identity migration](https://github.com/langbot-app/langbot-plugins/blob/7ad54b1a139d88113bc55128326800ed29779737/Runner/dify-agent/SHARED_RUNTIME.md#upstream-identity-migration).
An older bare-ID source revision also passed the old tests, but its manifest
versions are below Core's migration minimums. It is intentionally not used to
claim current compatibility.

To run with an official checkout at the locked revision:

```bash
export LANGBOT_LEGACY_PLUGIN_ROOT=/absolute/path/to/langbot-plugins
uv run --frozen pytest tests/unit_tests/agent/test_legacy_identity_boundary.py -q -rs
```

An unset variable allows an explicit local prerequisite skip. An empty variable,
a missing file, a path escaping the fixture root, or a hash mismatch fails.
CI selects the 16 consumer cases and requires all 16 to pass without skips.

## Embedded SeekDB

The job installs `uv sync --dev --extra seekdb --frozen`, using the versions and
wheel hashes already committed in `uv.lock`: pyseekdb 1.4.0.post1 and
pylibseekdb 1.4.0. It runs the existing two slow tests against a real embedded
engine, covering upsert/text preservation and full-text/hybrid relevance order.
The tests supply their own small embedding vectors; no model download is needed.

```bash
uv sync --dev --extra seekdb --frozen
uv run --no-sync pytest tests/integration/vector/test_seekdb.py \
  -m slow -q -rs --durations=5 --junitxml=seekdb-contract-results.xml
python scripts/assert-required-tests.py seekdb-contract-results.xml \
  --module tests.integration.vector.test_seekdb --expected-tests 2
```

This isolated Linux job keeps native dependency startup failures visible instead
of treating them as skips. JUnit results and native startup logs are uploaded
when available. A missing optional package or native engine failure is not
counted as a passing contract.
## Compiled CLI HTTP contract

The `Compiled CLI HTTP Contract` CI job runs the real `lbctl` process against a
loopback-bound Core HTTP server with temporary SQLite data and synthetic runtime
providers. It checks command parsing, API-key/workspace and capability discovery,
knowledge-engine/parser routes, sandbox diagnostics, pipeline extension updates,
pipeline execution, and monitoring reads. It does not need production accounts,
external model services, Docker, or a running LangBot deployment.

CI builds the official [`langbot-app/langbot-cli` v0.2.0 source](https://github.com/langbot-app/langbot-cli/tree/3bd20eecd4771b1fe5d0dca61d8b5523182e7bd9),
pinned to commit `3bd20eecd4771b1fe5d0dca61d8b5523182e7bd9`, using Go 1.26.8.
Module versions and checksums come from that checkout's `go.mod` and `go.sum`.
The job verifies modules and builds with `CGO_ENABLED=0`, `-mod=readonly`, and
`-trimpath`. It requires exactly one passing JUnit case and rejects skips.

To run locally with an official pinned CLI checkout and Go 1.26.8:

```bash
# In the official langbot-cli checkout:
git checkout 3bd20eecd4771b1fe5d0dca61d8b5523182e7bd9
export GOTOOLCHAIN=local CGO_ENABLED=0
go mod download
go mod verify
go build -mod=readonly -trimpath -o ./bin/lbctl ./cmd/lbctl
export LANGBOT_CLI_BIN="$(pwd)/bin/lbctl"

# In the LangBot Core checkout:
uv run --frozen pytest \
  tests/unit_tests/api/service/test_cli_diagnostics.py::test_compiled_cli_against_core_http \
  -q --tb=short -rs
```

Without `LANGBOT_CLI_BIN`, this test remains an explicit local skip. When set, it
must point to a real compiled executable. CI supplies an absolute path and treats
a missing binary, command failure, or skipped case as a failure. Update the source
pin deliberately and rerun the contract before accepting a newer CLI version.

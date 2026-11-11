# Plugin Dependency Management

## Desired-state artifact installations

LangBot sends marketplace, GitHub, and uploaded plugin packages to the Runtime
as digest-addressed artifacts. Before any enabled artifact worker launches, the
Runtime:

1. Parses the verified artifact's `requirements.txt` as PEP 508 requirements.
2. Installs dependencies into a writable staging target without modifying the
   Runtime's own Python environment.
3. Rejects symbolic links and verifies the installed distribution metadata.
4. Atomically publishes the dependency tree as read-only under
   `data/plugin-runtime/environments/sha256/<environment-digest>`.
5. Adds that tree to the matching worker's Python import path.

The environment digest includes the artifact and requirements digests, Python
ABI, Runtime version, installer schema, and Runtime profile. Therefore the same
verified artifact can reuse one immutable dependency tree across installations
without sharing writable plugin state. Concurrent preparation is serialized,
and a failure leaves no ready or half-published tree.

Apply and reconcile report `state=failed` with
`error_code=dependency_prepare_failed` and do not launch the worker when
preparation fails. Reapplying the same desired revision retries preparation.

Artifact `requirements.txt` files cannot contain pip control options such as
`--index-url`, `--extra-index-url`, or nested `-r` files. Index and trust
configuration is owned by the Runtime process through
`LANGBOT_PLUGIN_PYPI_INDEX_URL` and `LANGBOT_PLUGIN_PYPI_TRUSTED_HOST`.

## OSS development profile

The `oss_dev` profile runs pip directly with the Runtime interpreter and an
allowlisted subprocess environment. Pip writes only to the environment staging
target, and the worker continues to use the trusted Runtime interpreter while
loading the published dependency tree through `PYTHONPATH`.

Because `data/plugin-runtime` is the normal persistent Runtime volume, prepared
dependencies survive container recreation. Dependencies from different plugin
artifacts are never installed into the container-global virtual environment and
cannot overwrite one another.

On POSIX systems, the direct worker communicates with the Runtime over stdio.
On Windows, the Runtime still owns and reaps the child process, but the worker
uses the authenticated loopback WebSocket endpoint because asyncio subprocess
pipes are not compatible with the required Windows event-loop behavior.

## Shared multi-tenant profile

The `shared` profile prepares the same immutable environment inside a
policy-limited nsjail. Only the writable staging target and temporary directory
are exposed to pip. The completed tree is mounted read-only into each matching
plugin worker, while the trusted Runtime SDK path remains first on
`PYTHONPATH`.

## Legacy OSS installations

Older OSS installations stored under `data/plugins/<author>__<name>` keep their
compatibility path. At Runtime startup, each legacy plugin receives a local
`.venv` with `system_site_packages` enabled, its requirements are reconciled,
and the plugin is launched with that interpreter. This path is separate from
the desired-state artifact environment described above.

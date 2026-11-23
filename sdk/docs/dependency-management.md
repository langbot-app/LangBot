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

The digest covers the requirements bytes, worker ABI, Runtime version,
installer schema and profile. Shared runtimes also bind the tree to the exact
artifact. OSS release reuse is described below. Concurrent preparation within
a Runtime is serialized, and a failed install does not publish a ready tree.

Apply and reconcile report `state=failed` with
`error_code=dependency_prepare_failed` and do not launch the worker when
preparation fails. Reapplying the same desired revision retries preparation.

Artifact `requirements.txt` files cannot contain pip control options such as
`--index-url`, `--extra-index-url`, or nested `-r` files. Index and trust
configuration is owned by the Runtime process through
`LANGBOT_PLUGIN_PYPI_INDEX_URL` and `LANGBOT_PLUGIN_PYPI_TRUSTED_HOST`.

## OSS development profile

The `oss_dev` profile runs pip with the Runtime interpreter and an allowlisted
subprocess environment. Releases by the same author with the same plugin name,
requirements bytes, Python marker environment, wheel ABI, pip version and
package source reuse one read-only tree. A code-only upload can start offline.
Each worker still runs the code from its own verified artifact.

Changing the requirements creates a fresh target. Pip can reuse cacheable
downloads from `data/plugin-runtime/pip-cache/` for the same plugin and
resolver. Index metadata may still need to be fetched. A direct URL requirement
keeps the environment artifact-specific. Pre-existing schema-3 trees also
remain available to their exact artifacts. Their markers lack package-source
information, so the first new release using this cache may need one cold install.

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

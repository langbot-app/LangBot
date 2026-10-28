# Published plugins in regression runs

`regression_ci.py` and `regression_job.py` default to the latest published
LocalAgent, LangRAG and GeneralParsers packages from the official LangBot
marketplace. Plugin preparation happens before business testing. Each run reads
`latest_version` once for each plugin, downloads that exact version, and fails
if metadata, downloads, package identity, installation or initialization fail.
There is no fallback to older releases, cached packages or a source checkout.

The source runner needs the normal Core/SDK dependencies, Docker and `lbctl`:

```sh
python tools/regression_ci.py --lbctl /path/to/lbctl --output /path/to/new-run
```

The released deployment runner uses its existing job profile:

```sh
python tools/regression_job.py run --profile tools/regression_profiles/job.json --output /path/to/new-run
```

The job's default `plugin_mode` is `published`; its suite's `plugins` entries
are replaced by the published preparation. Set `"plugin_mode": "profile"` in
the job JSON to explicitly use the suite's existing local/GitHub/marketplace
inputs. For source development, `regression_ci.py --plugins /path/to/langbot-plugins`
retains packaging from a source checkout.

Each published run keeps `plugins/manifest.json` and the downloaded ZIPs under
its output directory. The manifest records the official metadata/download URLs,
selected versions, SHA-256 hashes and installation readback (actual version,
enabled state and initialized status). Archive identity/version must match the
release metadata; the CLI must report that same version as enabled and initialized.
Dependency or SDK incompatibility is a preparation failure and is not downgraded.

To replay an earlier run, pass its manifest to the source runner:

```sh
python tools/regression_ci.py --lbctl /path/to/lbctl --output /path/to/replay --plugin-manifest /path/to/earlier/plugins/manifest.json
```

For the deployment runner, set `"plugin_manifest": "/path/to/earlier/plugins/manifest.json"`
in the job JSON. Relative paths are resolved from the job profile directory.
Replay downloads the recorded versions from the official marketplace without
querying latest metadata and requires the recorded hashes. Missing or changed
packages fail; retain the manifest and ZIPs as evidence. Supplied URLs cannot
redirect replay to another registry or add other plugin identities.

Installation uses `lbctl plugin install local --file <downloaded-ZIP> --wait`
so the installed bytes are the ones whose hashes were recorded. This exercises
published package compatibility and initialization; it does not exercise the
marketplace install/upgrade endpoint itself. Workflow callers must omit their
explicit `--plugins` argument to select the default published mode.

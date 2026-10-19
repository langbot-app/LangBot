# Explicit Box file export

A Runner calls `ctx.export_box_files(paths)` with a non-empty list of normalized
absolute paths inside its bound sandbox. The run's outbox is the recommended place
for deliverables. Writing a file alone does not deliver it; LocalAgent exposes an
`export_box_files` model tool and performs no final directory scan.

Core validates every selected file before registering any new handles. Missing,
unreadable, non-regular or symlinked paths, exceeded quotas and malformed runtime
responses fail the whole batch and retain its files. The selected-file reader runs
inside the existing Box with its original configuration and Workspace/generation
fencing. It opens directories and files without following symlinks and uses
nonblocking opens to avoid hanging on FIFOs.

The existing limits remain: 20 files and 50 MiB per call, 10 MiB per file, and
100 files / 50 MiB cumulatively per run. Raw SDK stdout is capped at 1 MiB per
stream including base64/JSON overhead, so transport may reject a batch below its
nominal file quotas. Only explicit SDK clipping notices are classified as
truncation; ordinary invalid JSON is not guessed to be a size failure. Quota
errors include the threshold, known actual value or lower bound, sandbox paths,
retention state and suggested action.

Successful acceptance returns opaque run-scoped handles and removes only selected
files whose content still matches the accepted bytes. Unselected files remain.
Cleanup failure is a warning on accepted handles; it must not cause duplicate
registration or delivery. Re-reading unchanged retained files reuses their IDs;
changed content or distinct source paths produces distinct handles. Already
submitted IDs are never returned for another delivery.

`message.completed.file_ids` attaches accepted files to automatic Pipeline output.
Explicit Agent replies use `ctx.reply_files()`. Platform-send failure after Core
acceptance terminates LocalAgent rather than regenerating or resending possibly
already-delivered files. Model export retries use ordinary paired tool-call
messages within the original tool/context/deadline budgets. There is no separate
two-attempt completion recovery loop. Streaming text already sent cannot be
retracted. Retention lasts only within the existing Box/run lifetime; expiry and
startup cleanup remain in effect.

## Coordinated dependency

This API requires the matching Core, LocalAgent and SDK implementation. The current
Core and LocalAgent uv locks pin SDK commit
`b300830b0e5339e7989be237efa811bedf761d55` from SDK PR #180. Published SDK 0.7.4 and
0.7.13 do not include the paths argument. LocalAgent rejects an older Runtime SDK
before preparing its file tool. Maintainers must coordinate the SDK release and
Runtime upgrade before release deployment.

The internal directory-collection helpers retain their strict bounded reads and
host-permission fallback; they do not define the explicit Runner export API.

## Regression checks

```bash
uv run --no-sync pytest tests/unit_tests/box -q
uv run --no-sync pytest tests/integration_tests/box/test_outbox_export.py -v -s
LANGBOT_LEGACY_PLUGIN_ROOT=/path/to/pinned/plugins uv run --no-sync pytest --required-suite local_agent -q
```

The Docker integration records uid/gid/mode, checks exact bytes from root-owned
0600 output using a non-root Core on Linux, verifies Box reuse and rejects
cross-run handle reuse. The required LocalAgent suite uses the integrity-checked
plugin source in `tests/fixtures/legacy_plugin_identity_sources.json`; Core,
Runtime, SQLite and Docker are real while the model and faults are scripted.
Cases cover selection, repair, streaming, tool-budget exhaustion, cleanup retry,
invalid response, timeout, real-ledger cancellation and no implicit export.

The opt-in `test_live_explicit_export.py` additionally needs dedicated
`BOX_LIVE_API_KEY` and `BOX_LIVE_MODEL` configuration. Its absence is a skip,
not evidence of a live-model acceptance run.

# Development SQLite repeat smoke

Executed on 2026-11-17 in the new Linux development environment, Python 3.12,
checkout-local editable SDK. Start: `2026-11-17T06:51:00.739347+00:00`.

**Result: 8 rounds, 24 case executions passed, 0 skipped, 0 failed.**
The harness exited 0. Requested duration was 60 seconds, with a 1-second interval;
the final complete round ended after approximately 64.3 seconds. The deadline
stops new rounds but never truncates an otherwise healthy in-flight round.

This ran against the **dirty development checkout** based on
`83b6b0607b426db3a35f8dbe22e556dfe96d0938`. Changes were still being assembled.
It is not evidence for a final immutable candidate SHA; rerun after committing.
It is repeated fresh pytest processes with real SQLite, not a long-lived Core,
PostgreSQL/S3, Runtime, model-understanding or one-hour endurance claim.

Command:

```sh
.venv/bin/python tools/entrypoints/skill_artifact_soak.py \
  --duration 60 --interval 1 --output .qa/phase4-repeat-smoke \
  'tests/integration/storage/test_skill_artifacts.py::test_skill_artifact_fixed_version_no_copies_and_restart[sqlite-database]' \
  'tests/integration/storage/test_skill_artifacts.py::test_skill_artifact_gc_never_deletes_package_or_other_reference[sqlite-database]' \
  'tests/integration/storage/test_skill_artifacts.py::test_skill_artifact_read_lease_cancel_releases_pin[sqlite-database]'
```

| Round | Wall seconds including pytest startup | Tests | Result |
| --- | ---: | ---: | --- |
| 1 | 8.562 | 3 | passed |
| 2 | 6.947 | 3 | passed |
| 3 | 6.556 | 3 | passed |
| 4 | 8.149 | 3 | passed |
| 5 | 6.454 | 3 | passed |
| 6 | 6.648 | 3 | passed |
| 7 | 6.643 | 3 | passed |
| 8 | 7.353 | 3 | passed |

Raw round logs/XML and `rounds.ndjson` were produced in the command's output
directory. Attach those sanitized files to the review delivery; this relative
workspace location alone is not a recipient-accessible evidence link.

Harness checks: `python -m unittest tools.tests.test_skill_artifact_soak -v`
passed 3 tests. Ruff check/format and documentation diff whitespace checks passed.
MCP skill `lbs index` and `lbs validate` completed successfully. Public docs were
updated in English, Chinese and Japanese; their full site build was not run in
this task.

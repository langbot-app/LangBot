# Box outbox export failures

Runner file export reads only the bound run's outbox. A missing or empty
outbox is a successful empty read. Unreadable files/directories, I/O failures,
exceeded traversal/export limits, and malformed exec responses are failures.
They must not be converted into an empty or partial successful export.

If Core lacks permission to read host-mounted output, it retries the complete
read inside the already-bound Box. The retry preserves the Box configuration,
Workspace identity and generation checks. Both readers use the same bounded,
descriptor-relative implementation and do not follow symbolic links. Unsafe
host paths and quota failures do not trigger this permission fallback.

The existing limits remain: up to 20 files and 50 MiB per collection, with a
10 MiB per-file host limit. Exec transport retains its smaller 256 KiB per-file
limit and at most 5 MiB per collection. Over-limit output now fails explicitly
and remains in the outbox so the producer can reduce it and retry.

Runner export also checks its cumulative 100-file and 50 MiB run limits before
registering any new file handles or clearing the outbox. Failed reads and
rejected run budgets leave the existing handles and output files intact.
Cleanup follows successful acceptance, including a successful empty read.
This is retry protection within the current Box/run lifetime, not durable
archival; existing Box expiry and startup cleanup policies are unchanged.

## Regression checks

```bash
uv run pytest tests/unit_tests/box -q
uv run pytest tests/integration_tests/box/test_outbox_export.py -v -s
```

The Docker integration test prints the copied file's uid, gid and mode,
checks exact attachment bytes across two runs sharing one Box, and rejects
cross-run file references. Linux CI runs Core as a non-root user and must hit
the permission fallback for root-owned mode-0600 output. Docker Desktop has
different bind-mount ownership semantics, so its test explicitly selects the
remote reader; that result alone does not establish the Linux permission case.

When the sibling official LocalAgent source fixture is available, the original
`test_local_runner_owns_box_reuse_and_explicit_files` E2E additionally exercises
Core, Plugin Runtime, LocalAgent, Host file APIs and Docker with a scripted model.

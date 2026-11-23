# Host execution leases

A leased execution is a running `agent_run` started by the Host (`queue_name IS NULL`), or a `pending` `monitoring_messages` record. The row stores its Host process (`execution_owner_id`, a UUID chosen when the process starts) and an expiry (`execution_lease_expires_at`). While the owner is alive it keeps renewing the expiry. Once the expiry passes, any Host may mark the row as interrupted: the run becomes `failed` with `Execution interrupted: the LangBot host stopped renewing its lease.`, and the message becomes `error` with an `ExecutionInterrupted` monitoring error. Readers treat a `pending` message as live only while its lease is unexpired.

## Why there is a scope registry

Before LANG-326, each maintenance pass walked every active Workspace binding. Each Workspace cost one binding validation and two tenant transactions, run one after another. On cloud (about 3,000 Workspaces) one pass took about 140–150 s, which is longer than the 120 s lease. As a result, any execution longer than about two minutes was reaped by its own live Host. Its `finalize_run` then failed with `Cannot transition terminal run ... from failed to completed`, and the user saw "Request failed" even though the reply had been generated.

## Design

`execution_lease_scopes(owner_id, workspace_uuid, expires_at, generation)` is a global table with no row-level security. It names only a Host owner and a Workspace. Rows in it mean "this owner may hold leased rows in this Workspace".

- **Registration.** `register_execution_scope()` runs before the leased row is written, in its own short transaction, so a crash can never leave a leased row that no scope points at. It is an upsert that increments `generation`. Repeated registrations within one tick (20 s) are answered from memory.
- **Tick** (every 20 s; lease 120 s):
  1. Renew all of this owner's unexpired scopes with one `UPDATE`.
  2. For each of the owner's scopes, with at most 4 at a time, run one tenant transaction per model. That transaction renews the owner's rows, reaps expired rows in the Workspace, and checks whether the owner still holds live rows there. A scope with no live rows and no registration in the last lease period is deleted, but only if its `generation` is unchanged.
  3. Reap at most 50 expired scopes, which belong to dead or stalled Hosts. Before touching a Workspace, check its binding. If the Workspace belongs to another instance or is fenced, postpone the scope by 10 minutes. If the Workspace no longer exists, drop the scope. Delete a scope only after its owner has no live rows left in that Workspace.
- **Cost.** A tick costs O(Workspaces with in-flight executions on this Host + expired scopes), independent of the total number of Workspaces. Ticks never list Workspace bindings. The loop logs a warning when a tick takes longer than one third of the lease.
- **Expired leases are never adopted.** If an owner's lease lapsed, for example because its event loop stalled, its rows may already be reaped. When that owner later finishes the run, `finalize_run` may replace its own `failed`/interrupted state with the real outcome. This applies only when `execution_owner_id` is the current process. A different Host can never resurrect a run.
- **Upgrade.** Migration `0046_execution_lease_scopes` backfills scopes for rows that are already leased, so executions orphaned by the previous process stay reapable.

Tests: `tests/unit_tests/test_execution_lease_scopes.py` (SQLite) and `tests/integration/persistence/test_execution_lease_scopes_postgres.py`.

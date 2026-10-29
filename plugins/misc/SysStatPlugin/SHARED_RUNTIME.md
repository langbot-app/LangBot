# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

## Worker-scoped readings (not per-tenant)

Every value this command reports describes the **shared plugin worker** — its process and its
host — and is identical for all installations served by that worker:

- process RSS (`psutil.Process(os.getpid())`),
- host memory (`virtual_memory`) and host disk (`disk_usage('/')`),
- host CPU times, usage, logical/physical core count and current frequency.

None of it is tenant data and none of it is read from the calling installation's
configuration. It is intentionally exposed as worker/host status; treat it as operational
metadata for whoever can invoke the command, not as isolation between tenants.

## Non-blocking collection

- `psutil.cpu_percent(interval=None)` is used: it returns immediately with the delta since
  the previous call instead of sleeping for a one-second sample window.
- The whole collection is offloaded with `await asyncio.to_thread(_collect_status)`, so disk
  or procfs syscalls cannot stall overlapping invocations from other tenants.

## Per-invocation vs process state

- The command component is stateless: it reads no config and stores nothing on `self`.
- There is no binding-keyed cache, so `on_installation_revoked` needs no work here.

## Known limits

- Values are host-wide and shared across installations on the same worker; a tenant that is
  not permitted to see host statistics must not be granted this command.
- The first `cpu_percent(interval=None)` after a worker restart can report `0.00%` until a
  second sample establishes the delta.
- No claim of certification; independent review and two-Workspace invocation acceptance are
  still required.

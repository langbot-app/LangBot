"""Isolated operation-traceability subsystem.

The "成员操作日志溯源" (member operation traceability) feature lives entirely in
this package so it can be decoupled from the hot request path:

* :mod:`service` owns the capture levels, action catalog, append-only writer,
  tamper-evidence chain, dedupe window and read/prune APIs.
* :mod:`routes` exposes the governance / operation-log HTTP surface and is
  auto-discovered by the HTTP controller's package scan, so nothing in the
  Core controller package needs to import it.

How the decoupling keeps tracing off the hot path
-------------------------------------------------
Tracing is opt-in per Workspace. The Core route wrapper asks
:func:`operation_trace.service.is_globally_enabled` (a single module-level
boolean, no I/O) before it queues any trace work. While no Workspace has ever
turned tracing on, that flag is ``False`` and the wrapper performs zero
database round trips. The first time an operator enables tracing the service
flips the flag, and the per-Workspace level check then decides whether a given
request is recorded. Recording itself always runs *after* the handler released
its tenant scope, so auditing never extends a business transaction.
"""

from __future__ import annotations

__all__ = ['service', 'routes']

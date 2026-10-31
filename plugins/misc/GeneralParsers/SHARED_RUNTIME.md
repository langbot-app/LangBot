# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

- Configuration (`enable_vision`, `vision_llm_model_uuid`) is read per invocation through
  `self.get_config()`. Nothing from tenant config is copied onto the plugin, the Parser
  component or module globals, so a shared worker is never initialized with another
  installation's settings.
- The installation binding is resolved per invocation with
  `self.get_installation_binding()` and only used to derive a cache key; the binding
  object is not retained after the call.

## Binding-keyed state

- Parser telemetry (filenames, MIME types, extensions, durations, parse errors) is tenant
  data. It is no longer a process-global singleton: `TelemetryRegistry` keeps one
  `ParserTelemetry` per full installation scope
  `(instance_uuid, workspace_uuid, installation_uuid)`.
- `runtime_revision` is deliberately excluded from the scope so a worker upgrade keeps the
  same bucket.
- `GeneralParsersPlugin.on_installation_revoked(binding)` calls `release_telemetry(binding)`,
  dropping that installation's store on uninstall/disable/workspace-removal/upgrade.

## PDF execution boundary

- PyMuPDF is not thread safe and its table finder keeps module-level page state
  (`EDGES` / `CHARS` in `pymupdf.table`, unchanged across the supported 1.x line). Parsing
  it from the shared worker's thread pool let concurrent installations re-enter those
  globals and could return another installation's page text or crash the shared process.
- Every PDF parse therefore runs in a dedicated short-lived interpreter process
  (`components/general_parsers/isolated_process.py` + `process_worker.py`) that owns the
  complete lifecycle: open document -> font/header/footer pass -> `find_tables()` ->
  table extraction -> text/image extraction -> close document.
- The boundary is released only after that process has exited. A hard timeout
  (`DEFAULT_TIMEOUT_SECONDS`, 300 s), a cancellation or a crash terminates and reaps the
  worker before the caller resumes, so no dependency work can keep running into a later
  request. PyMuPDF module state only ever exists inside the per-parse worker; the shared
  process never imports it.
- Supported dependency range: `PyMuPDF>=1.24.0,<2.0.0` (see `requirements.txt`). The
  process boundary is what makes the shared runtime safe on this whole range; the range is
  bounded to the 1.x line this implementation is verified against.

## Page scoping

`PageRequest` carries no binding. `ParserObservabilityPage` resolves the current
installation from the task-local SDK binding (`self.get_installation_binding()`), which the
Host sets from the page request's installation context. `/snapshot` and `/clear` therefore
act only on the calling installation's store and never expose another installation's
filenames or errors. When no binding is active (direct, non-invocation use; unit tests) an
isolated "unscoped" store is used — it never receives records from a bound invocation.

## Known limits

- Telemetry is in-memory, per worker. It is not aggregated across workers and is lost on
  worker restart.
- The unscoped store is never merged into a tenant view; it exists only for direct use.
- No claim of certification; independent review and two-Workspace invocation acceptance are
  still required.

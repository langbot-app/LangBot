# Phase-five consumer integration review

Baseline: `0d5a5eea1`, branch `feat/3051-artifact-consumer-integration`.
Record the delivered full head SHA separately. This document describes contracts
and required evidence, not a claim that the verification matrix has passed.

## Compatibility and authority

The public Artifact ID is not a storage key or access grant. Consumers retain
references under their own business identity; releasing one consumer's reference
must not reclaim another consumer's bytes. Existing upload responses, indexing
`task_id`, run UUID `file_id` handles and delivery semantics remain compatible.
Run handles are not converted into unscoped account or plugin access.

Core and the checkout-local SDK change together. Source/Docker installations use
the in-tree SDK, but independently deployed Plugin Runtime and separately
installed plugin SDKs require explicit coordinated compatibility verification.
The new typed helpers reuse the existing Workspace action, not a new action or
capability flag. Use the Workspace catalog (including create `content_base64`)
for discovery. Older forwarding Runtime hops have only best-effort cancellation;
coordinated Runtime code propagates cancellation for Artifact Workspace calls.
Unsupported or ungranted Hosts fail visibly, without a legacy-storage fallback.
A successful Core unit test does not establish independent Runtime compatibility.
The existing released-SDK plugin support path must not be bypassed by silently
changing every plugin dependency pin. No SDK tag or release is part of this PR.

Knowledge-file Artifact imports retain their own business reference. The engine
continues to receive `storage_path` and use `get_knowledge_file_stream`; an
`artifact:<knowledge_file_uuid>` token is opaque. Core resolves it only after
checking the current installed engine against the knowledge base. Legacy uploads
and `file_id` inputs remain distinct valid paths, not authorization fallbacks
when an Artifact read is denied. Removing a file or base releases its holder,
not the owning principal's or another base's retained reference.

## Evidence required before merge

Record exact SHA, SDK source/version, backend, command, exit status, counts,
skips and sanitized logs for every executed row. Keep failed attempts and repairs
visible. Missing environments and opt-in skips are not passes.

| Boundary | Required independent observation |
| --- | --- |
| Plugin Workspace operations | Declared and currently granted installation only; deny missing grant, revoked/disabled installation, other installation and Workspace; owner ID not caller-supplied |
| Reference ownership | Multiple knowledge files/bases and owner retention share one underlying Artifact; deleting/releasing one preserves others; delete while held refuses |
| Legacy compatibility | Old upload response fields, indexing task ID, engine stream interface, run UUID handles and file delivery remain unchanged |
| SDK/Execution | Candidate and declared released SDK consumers; separately deployed Runtime without shared disk; unsupported Host fails visibly before any mutation |
| Storage/restart | Database and named S3, Core replacement/cache removal, byte/digest identity; no duplicate persisted byte store |
| Failure and races | Registration/read/import failure; cancellation; deletion/GC racing with reference creation; rollback and idempotent retry; no accessible partial result |
| Lifecycle | Consumer release never grants access; leases expire; business refs protect content until removed; isolated cleanup after process interruption |
| Models | Image and visual/text PDF understood through real authorized model; distinguish structured request bytes from semantic understanding; unsupported model visible |

Use the existing [cross-component suites](../../CROSS_COMPONENT_TESTING.md),
including `sdk_core`, `skill_persistence`, `skill_network` and affected
`network_plugin` paths. Only task-owned loopback services and fresh databases or
buckets may be used. Record any outstanding real PostgreSQL/MinIO, independent
Runtime, one-hour soak or model checks for reviewer execution; do not label
unit tests or short SQLite repetition as those results.

Evidence shared for review must not include credentials, environment files,
auth/config/state/database snapshots or personal data. Provide accessible logs,
XML/NDJSON, the exact candidate and reproduction commands. Do not automatically
merge or publish SDK releases.

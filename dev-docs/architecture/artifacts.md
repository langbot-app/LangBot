# Artifact service

Artifact references identify caller-owned files in a Workspace. The service is the authorization and lifecycle boundary; `ContentStore` remains the immutable byte store. IDs do not grant access and never expose storage keys, S3 locators or Box paths.

## Phase-one API

Only authenticated accounts and API keys are accepted. Each operation checks the Workspace execution fence, the required permission and the owning principal. Another account or key cannot read an asset merely by knowing its ID, including within the same Workspace. Plugin, processor, support-admin and run access is not enabled by this foundation. The operations have `exposure=none` and are excluded from plugin wildcard grants, SDK Workspace methods and default model tools.

| Workspace operation | HTTP | Permission |
| --- | --- | --- |
| `artifact.create` | `POST /api/v1/artifacts` (multipart `file`, optional `ttl_seconds`) | `resource.manage` |
| `artifact.get` | `GET /api/v1/artifacts/{id}` | `resource.view` |
| `artifact.read` | `GET /api/v1/artifacts/{id}/content?max_bytes=10485760` | `resource.view` |
| `artifact.retain` | `POST /api/v1/artifacts/{id}/retain` | `resource.manage` |
| `artifact.release` | `POST /api/v1/artifacts/{id}/release` | `resource.manage` |
| `artifact.delete` | `DELETE /api/v1/artifacts/{id}` | `resource.manage` |

HTTP and MCP execute the same ApplicationAPI operations and Artifact service. HTTP downloads use attachment disposition, `nosniff`, `private, no-store` and a digest ETag. The API provides complete bounded reads, not byte ranges or partial text extraction: an object larger than `max_bytes` is rejected. Uploads and reads are limited to 10 MiB. Field validation diagnostics retain their technical wording; owned business errors use the Workspace message language.

MCP tools are `create_artifact`, `get_artifact`, `read_artifact`, `retain_artifact`, `release_artifact` and `delete_artifact`. Creation accepts strict base64 with a pre-decode encoded-length limit; reads return base64 plus metadata. These are file transfer APIs. Structured image/PDF model consumption, user-attachment routing and Runner file conversion are later stages of #3051.

The existing file upload and Runner `file_id` APIs retain their contracts. No existing storage key or run handle is accepted as an Artifact ID. The separate `lbctl` client can continue using its existing routes; it has no Artifact commands in this phase.

## Lifecycle

Creation produces a temporary asset with a default 24-hour lifetime; callers may choose 1 second through 7 days. Retain creates a persistent caller-owned pin. Retain changes retention only, never authorization. Release removes the caller's pin and restores a 24-hour temporary grace period; repeated release does not keep extending the lifetime. Delete refuses an asset protected by a pin. Expired assets cannot be read or revived through retain.

Business references and GC serialize on the asset: an in-use object must not be removed while a concurrent retain succeeds. Delete commits a tombstone that rejects subsequent operations; physical cleanup is deferred to maintenance. An already-authorized immutable read may complete, or fail if external bytes are concurrently reclaimed. For expiry, maintenance first commits the tombstone in its own transaction. In the next transaction it deletes the database rows to check foreign-key protection before removing external bytes, then commits only after external deletion succeeds. A failure rolls back that transaction and retains the committed tombstone and locator for an idempotent retry. Database-backed bytes are removed transactionally. Failures are logged and do not restore access.

Creation inherits ContentStore's upload transaction behavior: cancellation rolls back the record and schedules external cleanup. A process crash before an S3 locator commits can leave an untracked upload; this phase does not add a bucket-wide orphan scanner.

Errors: missing, deleted and unauthorized asset IDs return 404 without disclosing existence; expired assets return `artifact_expired` (410); pinned deletion returns `artifact_in_use` (409); excessive reads return `artifact_too_large` (413); integrity failures return `artifact_integrity_failed` (422).

## Acceptance

Exercise authenticated HTTP and MCP against real persistence: byte-for-byte upload/download and digest, principal and Workspace isolation, limited permissions, expiry, retain/release/delete, malformed and excessive inputs, cancellation, GC concurrency and cleanup failure. PostgreSQL/MinIO acceptance includes restricted-role RLS and a second Core/restart reading persistent assets without shared cache roots. See [cross-component testing](../CROSS_COMPONENT_TESTING.md). A successful base64 transfer does not establish model understanding of an image or PDF.

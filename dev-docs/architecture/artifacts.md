# Artifact service

Artifact references identify caller-owned files in a Workspace. The service is the authorization and lifecycle boundary; `ContentStore` remains the immutable byte store. IDs do not grant access and never expose storage keys, S3 locators or Box paths.

## Phase-one API

Only authenticated accounts and API keys are accepted. Each operation checks the Workspace execution fence, the required permission and the owning principal. Another account or key cannot read an asset merely by knowing its ID, including within the same Workspace. Plugin, processor, support-admin and run access is not enabled by this foundation. The operations have `exposure=none` and are excluded from plugin wildcard grants, SDK Workspace methods and default model tools.

| Workspace operation | HTTP | Permission |
| --- | --- | --- |
| `artifact.create` | `POST /api/v1/artifacts` (multipart `file`, optional `ttl_seconds`) | `resource.manage` |
| `artifact.get` | `GET /api/v1/artifacts/{id}` | `resource.view` |
| `artifact.read` | `GET /api/v1/artifacts/{id}/content?max_bytes=10485760` | `resource.view` |
| `artifact.read_content` | `GET /api/v1/artifacts/{id}/read` | `resource.view` |
| `artifact.retain` | `POST /api/v1/artifacts/{id}/retain` | `resource.manage` |
| `artifact.release` | `POST /api/v1/artifacts/{id}/release` | `resource.manage` |
| `artifact.delete` | `DELETE /api/v1/artifacts/{id}` | `resource.manage` |

HTTP and MCP execute the same ApplicationAPI operations and Artifact service. HTTP downloads use attachment disposition, `nosniff`, `private, no-store` and a digest ETag. Raw downloads return the complete bounded object: an object larger than `max_bytes` is rejected. Structured content reads support the text and PDF ranges described below. Uploads and source reads are limited to 10 MiB. Field validation diagnostics retain their technical wording; owned business errors use the Workspace message language.

MCP tools are `create_artifact`, `get_artifact`, `read_artifact`, `read_artifact_content`, `retain_artifact`, `release_artifact` and `delete_artifact`. Creation accepts strict base64 with a pre-decode encoded-length limit; raw reads return base64 plus metadata. Runner file conversion and fixed-version Skill resources remain later stages of #3051.

The existing file upload and Runner `file_id` APIs retain their contracts. No existing storage key or run handle is accepted as an Artifact ID. The separate `lbctl` client can continue using its existing routes; it has no Artifact commands in this phase.

`artifact.read_content` accepts `mode`, `offset`, `max_chars`, `page_start` and `page_end` and returns structured content elements. MCP `read_artifact_content` maps them to native text/image/embedded-PDF blocks without placing encoded bytes into a text result. Both use the same authorized reader as execution attachment reads.

## Agent attachment reads

Inbound platform inputs render text markers and attachment metadata only, independently of model vision support. `InputMedia` and the Host query registry retain original components; `prepare_input_files` also registers media found only in event contents before replacing those contents with markers. Runner descriptors contain no inline bytes, Host paths or source URLs. No eager download is introduced. The existing raw `read_input_attachment` API and new structured `read_input_attachment_content` operation share the frozen `input_attachments` run grant, plugin installation identity and live run checks.

The first authorized platform attachment read creates a run-owned Artifact through the shared service. Only the Host's current-input registry may resolve an `att-N` ref; knowing another asset ID is not a grant. Run-owned assets do not become account-owned or publicly accessible. Agent debug accepts at most 20 distinct `artifact_ids`: it checks metadata with the original RequestContext before execution and stores the authorized set plus context in Host-only query fields. Synthetic event actors cannot select the asset owner. The separate Workspace management assistant still accepts text/approval turns only.

Structured reads use `auto`, `text`, `native` or `pages`, zero-based text `offset`, `max_chars` (8192 default, 16384 maximum), and one-based PDF `page_start`/`page_end` (at most ten pages). Results identify truncation and continuation offsets/pages. Auto mode returns structured images and UTF-8 text, and extracts PDF text. PDF text explicitly excludes images, layout and OCR. Native mode returns structured image/PDF content for a supporting provider; unsupported models fail visibly. Pages mode currently fails explicitly rather than implying that page rendering occurred. Raw bytes and structured content are returned only after source authorization; metadata and retained history do not contain base64 payloads.

## Lifecycle

Creation produces a temporary asset with a default 24-hour lifetime; callers may choose 1 second through 7 days. Retain creates a persistent caller-owned pin. Retain changes retention only, never authorization. Release removes the caller's pin and restores a 24-hour temporary grace period; repeated release does not keep extending the lifetime. Delete refuses an asset protected by a pin. Expired assets cannot be read or revived through retain.

Business references and GC serialize on the asset: an in-use object must not be removed while a concurrent retain succeeds. Delete commits a tombstone that rejects subsequent operations; physical cleanup is deferred to maintenance. An already-authorized immutable read may complete, or fail if external bytes are concurrently reclaimed. For expiry, maintenance first commits the tombstone in its own transaction. In the next transaction it deletes the database rows to check foreign-key protection before removing external bytes, then commits only after external deletion succeeds. A failure rolls back that transaction and retains the committed tombstone and locator for an idempotent retry. Database-backed bytes are removed transactionally. Failures are logged and do not restore access.

Creation inherits ContentStore's upload transaction behavior: cancellation rolls back the record and schedules external cleanup. A process crash before an S3 locator commits can leave an untracked upload; this phase does not add a bucket-wide orphan scanner.

Errors: missing, deleted and unauthorized asset IDs return 404 without disclosing existence; expired assets return `artifact_expired` (410); pinned deletion returns `artifact_in_use` (409); excessive reads return `artifact_too_large` (413); integrity failures return `artifact_integrity_failed` (422).

## Acceptance

Native PDF uses LiteLLM capability metadata or the administrator's explicit `pdf_input` model ability for a provider-confirmed alias. Unknown capability without that declaration fails explicitly. Content reads charge source materialization once per attachment, and separately cap cumulative returned content at the run read budget; the legacy raw-byte API continues to charge each full read.

Exercise authenticated HTTP and MCP against real persistence: byte-for-byte upload/download and digest, principal and Workspace isolation, limited permissions, expiry, retain/release/delete, malformed and excessive inputs, cancellation, GC concurrency and cleanup failure. PostgreSQL/MinIO acceptance includes restricted-role RLS and a second Core/restart reading persistent assets without shared cache roots. See [cross-component testing](../CROSS_COMPONENT_TESTING.md). A successful base64 transfer does not establish model understanding of an image or PDF.

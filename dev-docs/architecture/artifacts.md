# Artifact service

Artifact references identify account-owned files and run-owned attachments or outputs in a Workspace. The service is the authorization and lifecycle boundary; `ContentStore` remains the immutable byte store. IDs do not grant access and never expose storage keys, S3 locators or Box paths.

## Account API

The account-facing operations accept only authenticated accounts and API keys. Each operation checks the Workspace execution fence, the required permission and the exact owning principal, or the named manager of a published run output. Another account or key cannot read an asset merely by knowing its ID, including within the same Workspace. Unpublished run assets use the separate, live-run-authorized ExecutionAPI paths below. These Workspace operations have `exposure=none` and are excluded from plugin wildcard grants, SDK Workspace methods and default model tools.

| Workspace operation | HTTP | Permission |
| --- | --- | --- |
| `artifact.create` | `POST /api/v1/artifacts` (multipart `file`, optional `ttl_seconds`) | `resource.manage` |
| `artifact.get` | `GET /api/v1/artifacts/{id}` | `resource.view` |
| `artifact.read` | `GET /api/v1/artifacts/{id}/content?max_bytes=10485760` | `resource.view` |
| `artifact.read_content` | `GET /api/v1/artifacts/{id}/read` | `resource.view` |
| `artifact.retain` | `POST /api/v1/artifacts/{id}/retain` | `resource.manage` |
| `artifact.release` | `POST /api/v1/artifacts/{id}/release` | `resource.manage` |
| `artifact.delete` | `DELETE /api/v1/artifacts/{id}` | `resource.manage` |
| `artifact.publication.get` | `GET /api/v1/artifacts/producers/{type}/{id}/publication` | `resource.view` |
| `artifact.publication.set` | `PUT` on the publication URL, `{enabled: bool}` | `resource.view` + `resource.manage` |
| `artifact.publication.disable` | `DELETE` on the publication URL | `resource.view` + `resource.manage` |

HTTP and MCP execute the same ApplicationAPI operations and Artifact service. HTTP downloads use attachment disposition, `nosniff`, `private, no-store` and a digest ETag. Raw downloads return the complete bounded object: an object larger than `max_bytes` is rejected. Structured content reads support the text and PDF ranges described below. Uploads and source reads are limited to 10 MiB. Field validation diagnostics retain their technical wording; owned business errors use the Workspace message language.

MCP tools are `create_artifact`, `get_artifact`, `read_artifact`, `read_artifact_content`, `retain_artifact`, `release_artifact` and `delete_artifact`. Creation accepts strict base64 with a pre-decode encoded-length limit; raw reads return base64 plus metadata. Fixed-version Skill resources remain a later stage of #3051.

The existing file upload and Runner `file_id` APIs retain their contracts. No existing storage key or run handle is accepted as an Artifact ID. The separate `lbctl` client can continue using its existing routes; it has no Artifact commands in this phase.

`artifact.read_content` accepts `mode`, `offset`, `max_chars`, `page_start` and `page_end` and returns structured content elements. MCP `read_artifact_content` maps them to native text/image/embedded-PDF blocks without placing encoded bytes into a text result. Both use the same authorized reader as execution attachment reads.

## Agent attachment reads

Inbound platform inputs render text markers and attachment metadata only, independently of model vision support. `InputMedia` and the Host query registry retain original components; `prepare_input_files` also registers media found only in event contents before replacing those contents with markers. Runner descriptors contain no inline bytes, Host paths or source URLs. No eager download is introduced. The existing raw `read_input_attachment` API and new structured `read_input_attachment_content` operation share the frozen `input_attachments` run grant, plugin installation identity and live run checks.

The first authorized platform attachment read creates a run-owned Artifact through the shared service. Only the Host's current-input registry may resolve an `att-N` ref; knowing another asset ID is not a grant. Run-owned inputs do not become account-owned or publicly accessible. Agent debug accepts at most 20 distinct `artifact_ids`: it checks metadata with the original RequestContext before execution and stores the authorized set plus context in Host-only query fields. After the run ledger starts, the Host atomically binds those authorized assets to that exact run. Subsequent reads require both the binding and a valid ledger lease; finalization releases the references, and crashed runs lose protection when their lease expires. Synthetic event actors cannot select the asset owner. The separate Workspace management assistant still accepts text/approval turns only.

Structured reads use `auto`, `text`, `native` or `pages`, zero-based text `offset`, `max_chars` (8192 default, 16384 maximum), and one-based PDF `page_start`/`page_end` (at most ten pages). Results identify truncation and continuation offsets/pages. Auto mode returns structured images and UTF-8 text, and extracts PDF text. PDF text explicitly excludes images, layout and OCR. Native mode returns structured image/PDF content for a supporting provider; unsupported models fail visibly. Pages mode currently fails explicitly rather than implying that page rendering occurred. Raw bytes and structured content are returned only after source authorization; metadata and retained history do not contain base64 payloads.

## Runner output files

`RunnerBoxService.export_files` stores each selected sandbox file as a temporary `run_output` Artifact. The complete batch is registered in one tenant transaction before handles are accepted or sandbox sources are removed. A registration failure leaves the sources and prior accepted handles intact. Source cleanup failure after acceptance returns a warning with the accepted IDs; it must not cause repeat delivery.

The public `BoxFile.id` remains the existing UUID run handle. Its metadata additionally contains `artifact_id`, `mime_type`, `digest`, `lifecycle` and `expires_at`, with no inline bytes. `execution.read_run_file` resolves that handle through its run's export registry and returns bounded structured content using the shared reader. A previously submitted file remains readable while the original run is active, but cannot be submitted again. Platform replies resolve the registered bytes through ArtifactService; Core and Runtime need no shared file roots.

`execution.commit_run_files` validates the entire batch against the original live run and an explicit producer publication policy. `artifact.publication.set` records only the authenticated account or named Workspace API key as recipient; neither generic producer config nor Runner arguments can select the manager. A policy is self-owned, is absent for new/copied producers, and retains its owner when disabled. Its revision is frozen in Host-only query state at run start. Commit locks and revalidates the enabled policy, producer existence, current active account/membership permissions or API-key status/expiry/scopes. Global/legacy compatibility keys, platform actors, Workspace owners and key creators are not implicit recipients. Policy changes or revocation invalidate an old frozen grant.

Publication preserves `owner_type='run_output' / owner_id=origin_run` and atomically sets `manager_type/id` plus the standard `principal` pin. The named manager then uses the existing account Artifact API after run completion or restart. Repeat commit is one-shot and cannot restore a pin explicitly released by that manager; retain is the manager's operation. A manager conflict rejects the whole batch. Export, read and delivery do not publish, and commit is not a default model tool. The original run/session, installation, Workspace fence and frozen sandbox grant still apply. Another run must receive an explicit input binding. No generic run-file HTTP endpoint is added.

The orchestrator's `finally` attempts bounded cleanup to expire unpublished outputs on completion, failure or cancellation. Published outputs retain their manager's chosen retention, including a release grace period. Maintenance physically collects expired output content through the same tombstone rules below. Core crashes, cleanup failures and timeouts leave the original 24-hour expiry as the fallback. Retaining bytes does not provide run resumption.

The earlier, unshipped phase-three branch used private `run_output_commit` pins with no proven named manager. Migration preserves those rows and bytes without exposing them or guessing a Workspace owner. They cannot be published through a retry. An operator upgrading such a pre-release instance must explicitly audit and map each legacy output to a currently authorized named principal, atomically establish its manager and standard principal pin, then remove the legacy pin. Fresh installations never create these pins.

## Lifecycle

Creation produces a temporary asset with a default 24-hour lifetime; callers may choose 1 second through 7 days. Retain creates a persistent caller-owned pin. Retain changes retention only, never authorization. Release removes the caller's pin and restores a 24-hour temporary grace period; repeated release does not keep extending the lifetime. Delete refuses an asset protected by a pin. Expired assets cannot be read or revived through retain.

Business references and GC serialize on the asset: an in-use object must not be removed while a concurrent retain succeeds. Each download commits a 120-second `read_lease` before bounded object-store I/O (60-second deadline), then releases it without holding a DB transaction during download. The exact originating run and explicitly bound input runs are protected by the existing execution/claim ledger lease, without another heartbeat. Internal authorized run reads can continue past temporary expiry while that lease is valid; account reads still obey expiry. Release ignores transient read/run references when restoring the 24-hour grace period, so a crashed consumer cannot leave an immortal asset. GC prunes invalid leases and references before reclamation.

Delete commits a tombstone that rejects subsequent operations; physical cleanup is deferred to maintenance. For expiry, maintenance first commits the tombstone in its own transaction. In the next transaction it deletes the database rows to check foreign-key protection before removing external bytes, then commits only after external deletion succeeds. A failure rolls back that transaction and retains the committed tombstone and locator for an idempotent retry. Database-backed bytes are removed transactionally. Failures are logged and do not restore access.

Creation inherits ContentStore's upload transaction behavior: cancellation rolls back the record and schedules external cleanup. A process crash before an S3 locator commits can leave an untracked upload; this phase does not add a bucket-wide orphan scanner.

Errors: missing, deleted and unauthorized asset IDs return 404 without disclosing existence; expired assets return `artifact_expired` (410); pinned deletion returns `artifact_in_use` (409); excessive reads return `artifact_too_large` (413); integrity failures return `artifact_integrity_failed` (422).

## Acceptance

Native PDF uses LiteLLM capability metadata or the administrator's explicit `pdf_input` model ability for a provider-confirmed alias. Unknown capability without that declaration fails explicitly. Content reads charge source materialization once per attachment, and separately cap cumulative returned content at the run read budget; the legacy raw-byte API continues to charge each full read.

Exercise authenticated HTTP and MCP against real persistence: byte-for-byte upload/download and digest, principal and Workspace isolation, limited permissions, expiry, retain/release/delete, malformed and excessive inputs, cancellation, GC concurrency and cleanup failure. PostgreSQL/MinIO acceptance includes restricted-role RLS and a second Core/restart reading persistent assets without shared cache roots. See [cross-component testing](../CROSS_COMPONENT_TESTING.md). A successful base64 transfer does not establish model understanding of an image or PDF.

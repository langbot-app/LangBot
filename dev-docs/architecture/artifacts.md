# Artifact service

Artifact references identify account-owned files and run-owned attachments or outputs in a Workspace. The service is the authorization and lifecycle boundary; `ContentStore` remains the immutable byte store. IDs do not grant access and never expose storage keys, S3 locators or Box paths.

## Account API

The account-facing operations accept only authenticated accounts and API keys. Each operation checks the Workspace execution fence, the required permission and the exact owning principal, or the named manager of a published run output. Another account or key cannot read an asset merely by knowing its ID, including within the same Workspace. Unpublished run assets use the separate, live-run-authorized ExecutionAPI paths below. The principal-private create/get/read/read_content/retain/release/delete operations also support installed plugins under the phase-five boundary below. Skill-source creation and publication policy operations retain `exposure=none` and remain unavailable to plugins.

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

MCP tools are `create_artifact`, `get_artifact`, `read_artifact`, `read_artifact_content`, `retain_artifact`, `release_artifact` and `delete_artifact`. Creation accepts strict base64 with a pre-decode encoded-length limit; raw reads return base64 plus metadata. Fixed-version Skill resources use the source boundary described below.

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

Artifact release/deletion governs its own stored content, not independently retained platform or monitoring history. The existing `MediaReferenceText` contract externalizes recognized inline images; delivered `File.base64` history retains its existing representation and retention. Artifact row/object reclamation is therefore not a claim that every delivered copy has disappeared.

Errors: missing, deleted and unauthorized asset IDs return 404 without disclosing existence; expired assets return `artifact_expired` (410); pinned deletion returns `artifact_in_use` (409); excessive reads return `artifact_too_large` (413); integrity failures return `artifact_integrity_failed` (422).

## Acceptance

Native PDF uses LiteLLM capability metadata or the administrator's explicit `pdf_input` model ability for a provider-confirmed alias. Unknown capability without that declaration fails explicitly. Content reads charge source materialization once per attachment, and separately cap cumulative returned content at the run read budget; the legacy raw-byte API continues to charge each full read.

Exercise authenticated HTTP and MCP against real persistence: byte-for-byte upload/download and digest, principal and Workspace isolation, limited permissions, expiry, retain/release/delete, malformed and excessive inputs, cancellation, GC concurrency and cleanup failure. PostgreSQL/MinIO acceptance includes restricted-role RLS and a second Core/restart reading persistent assets without shared cache roots. See [cross-component testing](../CROSS_COMPONENT_TESTING.md). A successful base64 transfer does not establish model understanding of an image or PDF.

## Skill package sources (phase four)

`artifact.skill_resource.create` (`POST /api/v1/artifacts/skill-resources`, MCP
`create_skill_resource_artifact`) accepts `skill_name`, an explicit `revision`,
`path`, and optional `ttl_seconds`. Creation requires both source viewing and
Artifact management permission. Like other account Artifact operations, it has
`exposure=none`: no plugin Workspace grant, generated Workspace SDK method,
default model management tool or `lbctl` command is added.

The four source decisions are:

1. **Identity.** Resolve name and revision at registration, then bind the immutable
   version UUID, package content reference and canonical file path. File digest,
   size and MIME describe the selected file, not the archive. Later reads resolve
   the stored version identity, never `latest` or the current Skill name. Repeated
   registration for one owner/version/path returns the same deterministic ID,
   without renewing expiry. An expired or deleted reference must be collected
   before that identity can be registered again.
2. **Authorization.** A Workspace reference is owned by its creating account or
   API key; knowing the ID, sharing Workspace membership or adding a retention
   pin grants nothing. Run consumers must use the existing installed ExecutionAPI
   tool path and frozen activated-Skill revision, not a new arbitrary by-ID action.
   A Workspace Skill source cannot be converted into an ordinary run input to
   bypass that source authorization. Run-owned sources use the existing
   `call_tool` installation authorization, persisted `activated_skills` revision
   and live run lease; every read rechecks the bound run. No generic source
   publication or cross-run by-ID action is added.
3. **Lifecycle.** A source Artifact references the existing package and retained
   version. Its foreign-key protection and ordinary read leases protect the
   package while live metadata or a read still depends on it. Artifact GC deletes
   only source-reference metadata, never bytes owned by the Skill subsystem.
   Removing the current Skill catalog entry leaves retained versions intact.
   This is not a new package-version GC policy or a promise that a retained
   package is deleted when its last Artifact disappears. Migration 0052 refuses
   downgrade while source references remain, preventing an older reader from
   mistaking package bytes for the selected file.
4. **Storage.** Use the database Skill repository's authoritative immutable
   package, integrity checks and bounded archive reader. Artifact source reads
   share the legacy resource path's per-Core bounded LRU archive cache (32 MiB,
   at most 256 entries), not a separate cache or durable copy. Every read still
   validates the live scoped version/content metadata, digest and manifest, and
   source authorization; a cache hit is not permission to read. A cold replacement
   Core fetches the package from authoritative storage. Do not copy individual
   files or whole packages into Artifact-owned ContentObjects. Clearing caches
   does not change source identity. Filesystem-only packages fail explicitly
   rather than falling back to mutable paths or copying into a second store.

The existing `read_skill_resource` text result remains compatible. Database-backed
run Skill registration verifies bounded source bytes. Source materialization is
charged once per immutable Artifact per run, capped at 256 KiB per file and 1 MiB
per run. A separate 1 MiB per-run budget counts cumulative returned JSON UTF-8
and media payload bytes. Every continuation reauthorizes the source even when
its materialization was previously charged. The legacy text path is unchanged.
Structured binary results must go through the shared Artifact reader and existing
model content adapters; a base64-bearing ordinary string is not model media input.
Native PDF capability checks and the lack of page rendering remain unchanged.
See the [phase-four acceptance handoff](../review/artifact-phase4/README.md) for
verification boundaries; documented behavior alone is not acceptance evidence.


## Plugin and knowledge-file consumers (phase five)

The seven operations `artifact.create`, `get`, `read`, `read_content`, `retain`,
`release` and `delete` admit the plugin principal with `exposure=all`. The owner is
its trusted installation UUID, never a caller-selected author/name or account.
Every call revalidates the enabled current installation and effective grants,
including stale captured RequestContexts. A replacement installation UUID cannot
read its predecessor's files. Declare operation IDs individually: `artifact.*`
expands to account-only Skill/publication operations too and is therefore rejected.
Account/Skill/run resources are not converted into plugin-owned assets.

Plugin JSON RPC creation uses bounded `content_base64`; decoding and raw plugin
reads have a 256 KiB ceiling. Raw reads return `metadata` and `content_base64`;
structured reads use the existing shared reader. Existing HTTP bytes and account
upload/download responses remain unchanged. Retain is an installation-private
pin, not a grant; deleting while any live business reference remains is refused.

`knowledge.file.store_artifact(kb_uuid, artifact_id, parser_plugin_id=None)` is
an account/API-key operation and HTTP `POST /api/v1/knowledge/bases/{kb_uuid}/files/artifact`;
MCP exposes `add_knowledge_file_artifact`. It preserves the indexing task-ID
response and binds a durable knowledge-file holder to already-authorized bytes.
It rejects Skill/run sources rather than weakening their original restrictions.
KnowledgeEngine's legacy `get_knowledge_file_stream(storage_path)` resolves the
opaque `artifact:<knowledge_file_uuid>` token only for the currently installed
engine assigned to that knowledge base, then uses the common holder read. A token
is not a filesystem path or independent permission. Deleting a file/base releases
only its holder. Existing uploads and file IDs remain compatible; denied Artifact
reads must not fall back to unscoped legacy storage access.

SDK convenience proxies `self.plugin.artifacts` and `ctx.api.artifacts` use the
existing Workspace action, with no new protocol action or capability flag. They
return typed metadata and decoded bytes, while preserving Host business errors
as `ArtifactOperationError(code, details)`. A run proxy must also pass its live
run and frozen Workspace-operation boundary. Discover support in the existing
Workspace catalog, including the `content_base64` create schema; unsupported or
ungranted Hosts fail visibly and never fall back to a storage path. Independent
older Runtimes can forward the existing action, but cancellation across an older
hop is best effort. Coordinated Runtime code forwards cancellation for Artifact
Workspace calls; caller cancellation is not proof that a completed mutation was
rolled back. Existing upload fields and run UUID handles are unchanged.

Persistent legacy `/api/v1/files/images` and `/api/v1/files/documents` uploads keep
`file_key`/`file_id` and additionally return `artifact_id`. ContentAlias and
Artifact share one ContentObject. The alias has an independent durable holder;
its deletion releases only that holder. Nonpersistent legacy uploads retain only
the old response fields, and existing opaque keys are not automatically migrated.
Knowledge-file binding accepts only account/API-key-owned plain uploads; even
published run outputs remain excluded alongside Skill-package sources. A durable
knowledge-base deletion fence blocks new admissions. Failed or uncertain deletion
retains the holders and retryable fence instead of deleting possibly live bytes.

The convenience helpers accept Python bytes and return Pydantic metadata/data
(or structured elements), raising `ArtifactOperationError` on business failure.
Generated `workspace.artifact` methods instead retain the standard
`ok/result/error` envelope and JSON `content_base64` field. Shared plugin helpers
inherit the active invocation/run scope and cannot reuse an escaped invocation
after it ends; this is not a global plugin object that bypasses run authorization.

Knowledge-file lists add nullable `artifact_id`; digest/size/MIME are not new list
fields. The durable `KnowledgeBase.deleting` fence survives Core restart. Upstream
delete failure, cancellation or unknown outcome keeps the runtime, files and
holders; an explicit delete retry resumes cleanup. No new ingestion is admitted
until deletion completes. Active or interrupted ingestion blocks deletion before
fencing, rather than releasing a still-needed source.

# Runtime artifact cache

Box can receive an immutable package over its authenticated control connection,
verify it, and mount its own copy without a Core filesystem path. The protocol is
generic: it carries a tree manifest and digest, not Skill names or CRUD operations.
Both Core and Box need the coordinated SDK and a Runtime with POSIX
descriptor-relative file IO (Linux is the validated deployment). Explicit
`box.file_transfer_mode: network` connects native Skill execution and draft
publication to this protocol; legacy mode retains its shared-path behavior.

Only network mode reuses a fresh matching Docker status without probing unrelated
backends. Legacy mode retains the full backend readiness enumeration.

## Host boundary and transfer

`BoxService.prepare_skill_artifact(context, name, revision)` is an internal Host
API for an already-authorized pinned Skill. Its caller owns run/resource grants;
this method does not add a plugin, MCP, assistant or HTTP operation. It checks the
current Workspace placement and sandbox admission, checks the exact publication
metadata on every call, and validates the Runtime receipt. Database probes use
persisted manifest, size and archive digest without reading the body. Only a miss
fetches archive bytes; neither path rebuilds a persistent Core cache.

In database/network mode, Agent resource listings validate the authoritative
immutable manifest without blob IO. Listing and activation are not content health
checks: they can succeed with an unavailable or corrupt blob.

For content reads, Core keeps a private process-local LRU of complete verified ZIP
bytes, bounded to 32 MiB and 256 entries, with no user configuration. Every request
still checks current Workspace scope, placement generation, version and content-ref
metadata in the database, then checks archive SHA and uses the SDK to verify the
complete ZIP/CRC and every file SHA. Only a successful SDK read admits those same
immutable bytes to the cache. The budget covers retained cache bytes, not in-flight request
memory; no local persistent cache or restored tree is created.

A verified cached copy remains readable when its source blob is offline or corrupt;
content reads therefore are not source-storage health checks either. Cold reads,
process restart and eviction require fetching and validating the source again.
Database failure, revoked access or missing version/content-ref records still
reject a cached read. Runtime execution's full byte validation, pins and GC are
unchanged by this Core memory cache.

`BoxArtifactDescriptor` contains `content_digest`, `manifest`, `archive_size` and
`archive_sha256`. `ActionRPCBoxClient.prepare_artifact` first probes the Runtime;
only a miss transfers the archive using the existing namespace-owned `FILE_CHUNK`
protocol. `PREPARE_ARTIFACT` consumes the completed transfer. Transport ownership,
trusted instance/Workspace context, generation fences and sandbox admission apply
to hits and misses. There is no caller-supplied download URL or user API token.
Box INIT can negotiate fixed 256 KiB chunks in both directions, reducing serial
round trips without changing archive bytes. Older peers retain 16 KiB sends;
ordinary plugin connections retain their original limits. File size, integrity,
ordering and ownership checks still apply. Each connection direction admits one
large chunk through encoding and ACK at a time, preventing concurrent files from
queuing large messages ahead of control actions.
Other actions do not acquire this file-send lock. Receive decoding uses the
existing write lock; the original action admission limits still apply.

`BoxSpec.artifact_mounts` selects a `BoxArtifactMountSpec` by digest. Runtime
resolves it inside the authorized Workspace cache into a generic read-only mount
at `/opt/langbot-artifacts/<digest>`, then uses the existing backend. Core's
untrusted execution payloads reject this field; Host orchestration composes it only
from authorized run pins before each execution. A cached digest is not a capability.

Native execution sends those references directly. Runtime fully validates the
scoped cache before session acquisition. Only a typed cache-preflight failure,
guaranteeing that the user command has not started, permits Core to prepare the
authorized publications and retry once. Warm execution does not read package
metadata in Core. Generic backend errors, timeouts, cancellation and session
errors are never replayed. Network INIT must acknowledge this preflight contract;
the client recognizes its error only from the transport's exact exception prefix.

Archive bytes are limited to 64 MiB. This is separate from the attachment upload
limit. Backend projection limits still apply, including E2B's 10 MiB per-file
limit. Tree validation also limits file count and total expanded size. Publication
rejects extra/missing files, unsafe paths, links, special files and byte/digest
mismatches. Failed preparation leaves no executable partial tree.

Draft registration uses the existing authenticated download action with
`directory_archive=true`. Runtime reads a stable, link-free tree into a bounded
in-memory ZIP_STORED archive: 20 MiB, 512 entries, 16 MiB per file, 64 MiB expanded
and depth 16. Lower file-transfer limits also apply. The session lease, execution
lock, admission and generation checks cover archive creation and file transfer;
sources inside or containing an additional mount are rejected. The usual file
chunks and digest receipt carry the archive to Core, which validates it and
publishes with revision CAS. For a complete replacement draft, Core checks
`base_revision` against the current database revision and performs the final CAS
without fetching or restoring the old package. Historical versions and the original
`created_at` are retained. No workspace snapshot is created; rejection and
cancellation retain the original draft. Network INIT acknowledges this capability.

Runtime removes a network workspace only after its backend stops. If Docker left
foreign-owned private directories, Runtime uses a bounded cleanup container from
the original immutable image, then confirms that helper has stopped before
removing the empty, inode-verified root. This path requires Docker 25+, Python 3
in the image and no declared image volumes. It preserves daemon user namespaces
and isolation controls. Unmapped ownership or a denied cleanup keeps the session
fenced for a later retry or operator maintenance.

## Cache ownership and lifecycle

The root belongs to Box's identity data directory, outside the writable sandbox
workspace and Core cache. Preparation requires the Runtime's exclusive identity
lock; a second owner cannot initialize or use this cache. Entries are scoped by Runtime instance, Workspace and
tree digest. Runtime publishes a verified sealed tree atomically. Local cache
state is disposable; source publications remain in the Core repository.

Use acquisition and GC share a lock. Acquisition protects queued/new executions
before session creation; mounted versions remain pinned until backend and managed
process cleanup completes. Session reuse can therefore retain more than one
revision without changing an existing mount underneath a process. Cancellation or
failed cleanup must not release a still-mounted version.

Each execution fully validates its pending cache lease. Adding that same protected
lease to the session checks scope, owner and directory identity under the GC lock
without hashing the tree again. Later executions still perform full validation.

`box.limits.max_artifact_cache_bytes` bounds reusable trees and metadata to a
default and maximum of 268435456 bytes. `artifact_cache_ttl_sec` defaults to 300,
with a maximum of 86400 seconds. A fixed 256-entry limit also bounds metadata and
filesystem entries. Changing either configured limit after the cache is first
used requires restarting Box Runtime. Idle entries can expire; capacity pressure evicts
unused entries. If protected entries consume the budget, preparation fails instead
of evicting active mounts. Backend projections and writable workspaces retain
their separate limits and session lifecycle.

Runtime removes owned abandoned preparation directories and reclaims unused cache
entries. It never deletes a published database version or S3 object. An evicted
version must be authorized, transferred and verified again before execution.
Do not manually remove cache directories while their Runtime is using them.

Pins are persisted before a version can be mounted. After an unclean Runtime
exit, entries with an unfinished protection marker stay protected, even after a
new session reuses and releases them. They can consume the capacity budget until
maintenance; an ordinary clean restart does not strand idle entries. To reclaim
crash-protected entries, stop that Runtime and its callers, confirm that its old
backend sessions and managed processes have retired, then remove only its cache
under `LANGBOT_BOX_DATA_DIR/artifacts/<runtime-instance-id>` (colons in the ID are
encoded as `%3A`; the data root defaults to `data/box` when the environment variable
is unset). Restart to fetch and verify needed packages again. Other Runtime
identities, writable Workspace directories and durable publications are outside
this cleanup scope.

For deployment settings, see the public Runtime development guide. Database
publication and persistent-content authority are described in
[Skill persistence](SKILL_PERSISTENCE.md).

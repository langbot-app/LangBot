# Runtime artifact cache

Box can receive an immutable package over its authenticated control connection,
verify it, and mount its own copy without a Core filesystem path. The protocol is
generic: it carries a tree manifest and digest, not Skill names or CRUD operations.
Both Core and Box need the coordinated SDK and a Runtime with POSIX
descriptor-relative file IO (Linux is the validated deployment). Explicit
`box.file_transfer_mode: network` connects native Skill execution and draft
publication to this protocol; legacy mode retains its shared-path behavior.

## Host boundary and transfer

`BoxService.prepare_skill_artifact(context, name, revision)` is an internal Host
API for an already-authorized pinned Skill. Its caller owns run/resource grants;
this method does not add a plugin, MCP, assistant or HTTP operation. It checks the
current Workspace placement and sandbox admission, reads that exact publication
from the repository on every call, and validates the Runtime receipt. Database
package reads supply their persisted manifest without rebuilding a Core cache.

`BoxArtifactDescriptor` contains `content_digest`, `manifest`, `archive_size` and
`archive_sha256`. `ActionRPCBoxClient.prepare_artifact` first probes the Runtime;
only a miss transfers the archive using the existing namespace-owned `FILE_CHUNK`
protocol. `PREPARE_ARTIFACT` consumes the completed transfer. Transport ownership,
trusted instance/Workspace context, generation fences and sandbox admission apply
to hits and misses. There is no caller-supplied download URL or user API token.

`BoxSpec.artifact_mounts` selects a `BoxArtifactMountSpec` by digest. Runtime
resolves it inside the authorized Workspace cache into a generic read-only mount
at `/opt/langbot-artifacts/<digest>`, then uses the existing backend. Core's
untrusted execution payloads reject this field; Host orchestration composes it only
from authorized run pins before each execution. A cached digest is not a capability.

Archive bytes are limited to 64 MiB. This is separate from the attachment upload
limit. Backend projection limits still apply, including E2B's 10 MiB per-file
limit. Tree validation also limits file count and total expanded size. Publication
rejects extra/missing files, unsafe paths, links, special files and byte/digest
mismatches. Failed preparation leaves no executable partial tree.

Draft registration has a separate ingress limit: Core requests a link-free
ZIP_STORED snapshot inside Box, bounded to 20 MiB, 512 entries, 16 MiB per file
and depth 16. Lower configured file-transfer limits also apply. Core downloads
only its own snapshot path, verifies the receipt, then validates and publishes
with revision CAS; rejection leaves the original draft intact.

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

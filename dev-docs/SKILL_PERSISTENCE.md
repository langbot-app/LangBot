# Skill and persistent content storage

Fresh configuration uses `skills.persistence: database`, `storage.use: persistent`
and `box.file_transfer_mode: network`. Existing explicit choices remain intact;
LoadConfig fills older missing keys with filesystem/local/legacy. The constructor
fallbacks retain those compatibility semantics for embedding callers too.
Use coordinated Core SDK and Runtime builds: the published package pin is a
separate artifact from this source tree. Missing SDK capabilities and a connected
Runtime's incompatible handshake stop startup. Ordinary Runtime unavailability
retains OSS management access, but blocks an actual nonempty legacy import.
Completed imports do not require Runtime readiness. Disabling Box still permits
read-only Skills and management. See the public Skills guide for upgrade
steps and rollback boundaries.

Before HTTP, plugin, bot and tool producers start, database repositories import
accessible scoped filesystem publications. `SkillStore.publication_inventory`
strictly discovers current pointers and retained versions, including versions
whose registration was deleted. Export checks the complete tree and manifest.
A Workspace database lease fences concurrent importers; each version and its
checkpoint commit together. Final current pointers and completion commit together,
so retained history never becomes an accidental current version. Old writers must
be stopped during this window; a new importer lease cannot fence an old release.

The import keeps source files. `skills.migration.require_source` and
`storage.migration.require_source` make an explicitly expected old volume mandatory.
Without a recorded pending source or that expectation, a new replica cannot know
whether an absent volume once held data. Completed database records bypass source
IO entirely. Changing a pending source, corrupt bytes or conflicting existing
publications aborts startup instead of silently losing data. Local scoped assets
retain their keys; unscoped media can be claimed only by the OSS singleton.
Explicit S3 storage is not automatically relocated.

## Authority and version identity

`skill_registry` selects the current version within an instance/Workspace/name.
`skill_versions` retains its manifest, public metadata and `content_ref`.
`content_objects` owns immutable bytes or a named S3 locator;
`content_aliases` preserves existing mutable upload keys without modifying old
content. Composite Workspace foreign keys prevent cross-tenant references and
prevent deletion of content still referenced by a version or alias.

The version remains the SDK's `sha256-tree-v1` content-tree digest. The ZIP byte
digest is separate. SDK publication export preserves file bytes and executable
bits with deterministic ZIP headers; restoration validates the manifest, complete
archive, paths, file types, sizes and digests before publishing a read-only tree.
DB-backed archives are bounded to 64 MiB. Public JSON metadata normalizes YAML
date values to strings without changing the package or its version.

Publication uses a private temporary SDK store for the existing CRUD and package
validation rules. A tenant transaction performs the registry CAS and writes the
version and content. A failed update or batch publishes no partial catalog.
Deleting a registration retains its versions for authorized pinned runs.

## Reads and consumers

Lists, ordinary metadata and package downloads do not build filesystem caches.
SkillManager refreshes the database catalog at request/run boundaries; an active
run continues to use its pinned version. In legacy mode, resource reads and execution snapshots
restore the exact authorized publication under
`skills.root/.database-cache/tenants/<namespace>`. This directory is disposable,
but callers must not remove it while execution is using it. Legacy catalogs live
outside this cache and are not imported or modified by enabling database mode.
Explicit network mode returns path-free metadata and reads resources directly
from the verified archive without restoring a tree. Runtime cache probes use
scoped version/manifest/size/digest metadata; archive bytes are fetched only on a
miss. Both hits and misses retain placement and sandbox admission checks.

`GET /api/v1/skills/<name>/package?revision=<revision>` returns a ZIP with its
revision and byte digest headers. Authentication and Workspace resource-read
permission are required; the repository validates placement and resolves the
Workspace/name/version before reading content. A digest or opaque content ref
does not authorize private package access.

The same service is registered as `skill.package.get` with `exposure: none`.
HTTP clients can use the authenticated binary endpoint. Existing MCP,
assistant, plugin and Runner Skill operations retain their current permissions;
the binary package operation is not advertised to them. The Host can prepare a
pinned publication through the [Runtime artifact cache](BOX_ARTIFACT_CACHE.md)
without materializing a Core tree. Native script execution uses these references
when `box.file_transfer_mode: network` is explicitly enabled. Draft registration
downloads a bounded ZIP from Box and publishes through the same tenant CAS;
validation, cancellation before publication or a stale base cannot publish a
partial version. The original sandbox draft is retained.

Public media retains its existing anonymous HTTP contract. Writes require a
trusted Workspace scope and explicitly register `public_media`. Reads use an
exact media key and a SELECT-only PostgreSQL policy; the public scope clears the
OSS singleton Workspace setting. Private bytes cannot be exposed by giving them
a media-shaped filename. Scoped upload aliases continue to validate their
Workspace and placement through StorageMgr.

## Complete package publication from lbctl

`POST /api/v1/skills/<skill_name>/package` accepts multipart `file` and required `base_revision`. `/package/preview` uses the same fields with read-only Workspace semantics. Both validate the archive through the SDK in disposable staging, including the internal Skill name, executable modes and binary resources. Preview returns `base_revision`, `proposed_revision`, added/modified/deleted paths, required permissions and `can_publish`. Publication delegates to the existing `import_skill_zip` revision CAS, then returns the published Skill. The CLI verifies the resulting revision through `skill.get`.

The Application API registers `skill.package.preview` and `skill.package.publish` for account/API-key principals. Preview requires `resource.view`. Publication also requires `resource.manage`. Both have `exposure=none`. Their consumer is the authenticated CLI, while model-facing authoring uses the existing draft tools. Core adds these IDs to system capabilities for `lbctl skill push`. A stale base returns HTTP 409, a missing Skill returns 404, and a mismatched internal name or invalid archive returns 400. Preview uses disposable validation storage and read-only Workspace operations.

## Backend changes and cleanup

Content defaults to database bytes. Named S3 backends retain their endpoint,
bucket and region identity in each locator; credentials remain in configuration.
Changing the default backend affects new content and does not migrate history.
Historical configurations must retain their original names and endpoint,
bucket and region identities. Credentials may rotate; restart Core after changing
them.

Database bytes roll back with their publication. S3 writes use unique keys;
transaction completion gates remove only an attempt's uncommitted upload or a
deduplication loser. Application shutdown waits for owned cleanup tasks and closes
the shared provider pools. Published versions and old alias content are retained
conservatively; local media cleanup does not expire this persistent content.

A process crash can leave an S3 object whose transaction never committed. There
is no online content GC in this stage. To reclaim these objects, stop all writers,
wait for uploads/transactions to finish, and compare the configured backend's
owned `content/<workspace>/` keys against every committed locator in the primary
database. This requires maintenance access to all Workspaces, not an RLS-filtered
Workspace session. Confirm that the prefix is exclusive to this database; if
other databases share it, include their complete reference sets too. Delete only
absent keys older than the operational grace period.
Do not use an age-only S3 lifecycle rule on the publication prefix: retained
versions can remain valid indefinitely. Keep every referenced content row and
every published version. Legacy import and default switching are tracked by #3010. Runtime-owned cache
GC is described in the artifact-cache contract above.

# Skill and persistent content storage

`skills.persistence: database` stores the Skill catalog and retained immutable
versions in the business database. `storage.use: persistent` also routes scoped
uploads and public media through the same content store. These are explicit
opt-ins; existing filesystem catalogs and local/S3 storage remain compatible.
Configuration and deployment limits are in the public Skills guide.
Existing Skill directories, uploads and media are not imported automatically.
Keep their original backend and migrate a populated deployment before switching;
persistent mode does not guess a legacy fallback for missing references.
Database Skills and package downloads require the coordinated SDK publication
helpers; the existing PyPI pin remains compatible with the filesystem default.

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
run continues to use its pinned version. Resource reads and execution snapshots
restore the exact authorized publication under
`skills.root/.database-cache/tenants/<namespace>`. This directory is disposable,
but callers must not remove it while execution is using it. Legacy catalogs live
outside this cache and are not imported or modified by enabling database mode.

`GET /api/v1/skills/<name>/package?revision=<revision>` returns a ZIP with its
revision and byte digest headers. Authentication and Workspace resource-read
permission are required; the repository validates placement and resolves the
Workspace/name/version before reading content. A digest or opaque content ref
does not authorize private package access.

The same service is registered as `skill.package.get` with `exposure: none`.
HTTP clients can use the authenticated binary endpoint. Existing MCP,
assistant, plugin and Runner Skill operations retain their current permissions;
the binary package operation is not advertised to them. Runtime package download
and replacement of execution mounts belong to the subsequent runtime work.
Current script execution still uses the existing Box mount contract.

Public media retains its existing anonymous HTTP contract. Writes require a
trusted Workspace scope and explicitly register `public_media`. Reads use an
exact media key and a SELECT-only PostgreSQL policy; the public scope clears the
OSS singleton Workspace setting. Private bytes cannot be exposed by giving them
a media-shaped filename. Scoped upload aliases continue to validate their
Workspace and placement through StorageMgr.

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
every published version. Automatic legacy import, default switching and Runtime
cache GC are separate stages tracked by #3010.

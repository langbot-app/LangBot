# Box instance identity

Startup cleanup removes only sandbox containers labeled with the current Box
instance ID. Containers owned by other instances, including unlabeled legacy
containers, are retained. Docker and Podman filter by both `langbot.box=true`
and `langbot.box.instance_id`; nsjail requires both a matching session prefix
and an exact `instance_id` in the session's `meta.json`.

Identity precedence is `lbp box --instance-id`, `LANGBOT_BOX_INSTANCE_ID`, then
`instance_id` in `LANGBOT_BOX_CONFIG`. IDs contain 1–128 ASCII letters, digits,
dots, colons, underscores or hyphens and start with a letter or digit. NsJail metadata
checks prevent overlapping prefixes from confusing two owners.

Without explicit configuration, Box generates `instance-id` in its data
directory once and reuses it after restarts. Choose the directory with
`--data-dir` or `LANGBOT_BOX_DATA_DIR`; the default is `data/box` relative to the
working directory. Give each deployment its own persistent directory. Preserve
it across container recreation; do not copy it when cloning an instance. If
persistence fails, Box uses a random ID, warns, and skips startup cleanup.

An OS file lock is held for the runtime lifetime. A second runtime using the
same ID and data directory is rejected before cleanup. Failure to create the
lock directory/file disables cleanup. Locks are released on shutdown or process
exit. Explicitly reusing an ID with different data directories or on different
hosts is not detected: operators sharing a Docker daemon must assign distinct
IDs and must not run two owners of one ID concurrently.

Core-managed subprocesses receive Core's stable instance UUID. Standalone and
sidecar runtimes establish their identity before accepting RPC connections;
INIT does not change ownership or trigger cleanup and rejects a different
`instance_id`. Configure their ID at launch
or use a persistent data directory. Box identity is separate from the trusted
Core identity used for authorization.

Cleanup logs list selected containers/directories. Other Docker owners are
excluded by the daemon-side filter; nsjail logs skipped directories at DEBUG.
No automatic unlabeled cleanup is provided. Old runtimes retain their old
cleanup behavior until upgraded, so upgrade all runtimes sharing a daemon
before relying on isolation from their startup cleanup.

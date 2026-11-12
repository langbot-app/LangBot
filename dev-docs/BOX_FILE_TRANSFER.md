# Box network file transfer

Issue #3010 adds file transport before Core attachment and Skill callers switch
to it. The SDK client uses the existing authenticated action RPC connection over
WebSocket or stdio. Core and Runtime need no shared directory for these calls.

## Client contract

`ActionRPCBoxClient.upload_file(session_id, path, content, action_context)`
accepts bytes and returns `path`, byte `size`, and a SHA-256 receipt.
`download_file(session_id, path, action_context)` returns bytes after checking
the receipt. Both require an existing session and an explicit trusted Workspace
context.

Paths must be normalized absolute POSIX file paths below the session's workspace
mount. Additional mounts, paths outside that workspace, links and non-regular
files are rejected. Uploading to a read-only workspace is rejected. This initial
contract does not read container-local files outside the workspace.

The Runtime enforces `box.limits.max_rpc_file_bytes` (default 20 MiB) per file.
A call transfers one file. Core's run-bound callers remain responsible for
attachment count, aggregate byte budgets and run authorization. ActionContext
binds instance, Workspace and placement generation; it does not carry a run ID.

## Transport and completion

Files use the existing 16 KiB FILE_CHUNK protocol. A high-entropy transfer key is
known before sending so cancellation can remove partial staging on the same
connection. Completed uploads are consumed by `box_upload_file`; downloads use
`box_download_file`. `box_delete_file_transfer` removes only staging owned by
the supplied context, including partial uploads. Cleanup accepts an old generation
without advancing the generation fence, so a handoff cannot strand its staging.

Workspace-scoped FILE_CHUNK requests retain their context and pass admission and
generation checks. Legacy context-free transfers remain supported, but cannot be
consumed by the new Workspace-scoped upload action.

The receiver keeps partial payloads private. Upload verifies size and SHA-256,
then publishes a complete workspace file through an atomic replacement. Retrying
the same path and bytes is safe. A timeout or cancellation after publication can
leave the complete new file, so callers must treat an interrupted acknowledgement
as an unknown outcome and may retry. Downloads do not delete the source.

Each chunk uses the existing 15-second RPC timeout. Upload publication and the
complete download RPC have 60-second timeouts. Cancellation requests peer cleanup;
local filesystem commits finish before their session lock is released. File IO
serializes with session execution and deletion, and holds a lease against idle
expiry. Temporary transfer payloads are deleted on completion/cancellation or
connection close. Cleanup failures are reported through the action or client log.

Transport is chunked, but these bounded SDK methods assemble one file in memory.
They are not an unbounded streaming API.

## Backends and rollout

Docker/Podman and nsjail use the Runtime's own workspace mapping. The explicit
unsafe host backend uses its managed workspace. These local backends require
descriptor-relative no-follow filesystem operations and a Runtime-visible
workspace. E2B transfers bytes with its native files API and uses private staging
plus bounded remote commands for safe workspace publication and download snapshots.

Existing Core attachment, export and Skill call sites remain on their current
paths in this stage. Stage 2 adopts file transport and stage 5 adopts Skill
transport. A caller using these methods needs a Runtime SDK containing the three
new Box actions; an older Runtime reports an unsupported action.

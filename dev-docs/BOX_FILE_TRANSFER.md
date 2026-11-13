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

Docker/Podman and nsjail use the Runtime's own workspace mapping. When a
Docker/Podman workspace file is inaccessible to the Runtime user, the existing
container's default user runs a bounded file helper. Upload bytes use stdin and
downloads use binary stdout with a separate size cap. The helper validates upload
length and digest before publication, and finishes cleanup before cancellation
releases the session lock. The explicit
unsafe host backend uses its managed workspace. These local backends require
descriptor-relative no-follow filesystem operations and a Runtime-visible
workspace. E2B transfers bytes with its native files API and uses private staging
plus bounded remote commands for safe workspace publication and download snapshots.

Existing Core attachment, export and Skill call sites remain on their current
paths in this stage. Stage 2 adopts file transport and stage 5 adopts Skill
transport. A caller using these methods needs a Runtime SDK containing the three
new Box actions; an older Runtime reports an unsupported action.

## Opt-in live verification

Run `sdk/tests/e2e/test_box_file_transfer_live.py` with
`LANGBOT_FILE_TRANSFER_BACKEND=docker`, `nsjail`, or `e2b`, one at a time.
Each invocation creates one sandbox, transfers at most 64 KiB per file, runs a
five-second checksum/copy command, and verifies cancellation and size rejection.
E2B creation is bounded to a 120-second lifetime. Docker requires an existing
`python:3.12-alpine` image. nsjail requires an authorized execution environment
and ancestor directories traversable by its mapped UID.

For self-hosted E2B, supply the existing `E2B_API_URL`, `E2B_SANDBOX_URL`,
`E2B_API_KEY` and optional `E2B_TEMPLATE`. The smoke uses a Docker-default Runtime
with one explicitly configured E2B session and clears the global E2B variables
after constructing that session's connection config. File transfer must retain
the session's backend, custom endpoints and reconnect routing headers.

Linux acceptance passed for Docker, nsjail and self-hosted E2B. Cleanup checks
query the exact Docker container, the nsjail session directory, or the exact E2B
sandbox across both running and paused states. The E2B query must first find the
created sandbox and then confirm its absence after deletion. This avoids
mistaking an unsupported detail endpoint's 404 for successful cleanup.

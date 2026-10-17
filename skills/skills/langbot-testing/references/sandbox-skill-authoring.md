# Skill publication and execution acceptance

Verify through Debug Chat that instructions and text resources work without Box,
and that executable packages use the revision activated by the current run.
API and direct backend checks diagnose failures; they do not establish UI acceptance.

## Preconditions

Use the frontend/backend and Local Agent pipeline selected in the machine's
`skills/.env.local`. The model must support tool calling. Do not record credentials.
Use Docker/Podman, nsjail, or a configured E2B service. The runner may acquire an
empty Box before activation; adding a revision must preserve that Box. Host mode
provides no sandbox isolation evidence.

## Read-only path

Install a unique Skill with instructions and a UTF-8 reference, then disable Box.
Ask the Agent to activate it and read the reference. Check the reported revision,
reference contents, and absence of sandbox creation. Execution requests must fail
clearly; activation must not claim that files are already mounted.

## Publish and execute

1. With Box enabled, create a draft under `/workspace/skill-drafts/<name>`.
   Include `SKILL.md`, `scripts/use.py`, and `data/input.json`. Resolve resource
   files relative to `__file__`; the script should print a deterministic marker.
2. Call `register_skill` with the draft path, then `activate`. Record revision v1.
3. Execute the script under the `mount_path` returned by activation. Write results to the
   run's outbox or draft directory, never the published package.
4. Attempt to overwrite a published file. The operation must fail and its contents
   must remain unchanged. Check UI results, tool logs, and the published package.

## Update an existing Skill

Copy v1 to a separate writable draft. Modify the draft and publish with
`base_revision=v1`; record v2. The existing run must continue reading/executing v1,
including when `activate` is called again. A new run in the same conversation must
activate v2. A stale `base_revision` update must fail. Removing the Skill from the
new run's authorization must not break startup or restore the old activation.
Verify a second UI edit/save adopts the revision returned by the first save.

## Shared Box and recovery

With nsjail, alternate two authorized runs using v1 and v2 in the same Box. Check
each script's independent version marker, retained `/tmp` state, and a running
managed process. Neither activation nor a changed mount set may recreate the Box.
Docker/Podman and E2B must likewise add v2 at its digest path while v1 and the
existing Box remain usable. On fixed-mount backends, changing ordinary host mounts must fail without
removing the session. Programs sharing a Box can see its cached packages; test
version consistency without claiming that the shared filesystem isolates runs.

Pins are Host-owned run ledger data, not conversation state. An active run whose
in-memory pin is reloaded must use its recorded revision, even after publication
or deletion of the current catalog entry. A missing recorded package must fail.
A Core process restart expires tool sessions; calls from those sessions must be
rejected. Do not report this as automatic run recovery.

Capture the visible assistant results, relevant tool logs, revisions, and file
contents. Public E2B credentials and deployment topology are separate prerequisites;
mocked or local backend results do not establish E2B service acceptance.

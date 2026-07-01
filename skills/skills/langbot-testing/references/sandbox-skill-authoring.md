# Sandbox Skill Authoring

## Goal

Verify that Local Agent can use sandbox tools to create, register, activate, and use a LangBot skill package through the same path a user would exercise in Debug Chat.

This flow applies to Docker, nsjail, and E2B backends. API calls are useful diagnostics, but the primary pass/fail signal is the model-driven Debug Chat tool sequence.

## Preconditions

1. Read `../.env` and use `LANGBOT_FRONTEND_URL` and `LANGBOT_BACKEND_URL`.
2. Start LangBot with the intended backend:
   - `BOX_BACKEND=e2b` when validating E2B.
   - `BOX_BACKEND=nsjail` when validating nsjail.
   - `BOX_BACKEND=local` or `docker` when validating local container fallback.
3. Confirm `/api/v1/box/status` reports `available: true` and the expected backend name.
4. Confirm Debug Chat uses a model with function-calling ability.
5. Confirm backend logs say native sandbox tools are available.

Do not store sandbox provider keys, JWTs, OAuth tokens, or localStorage values in the case or notes.

## Debug Chat Prompt Pattern

Use a unique skill name per run, for example:

```text
lb-sandbox-agent-e2e-<timestamp>
```

Send a prompt that requires the model to do all of the following:

1. Use `exec` to create a multi-file skill under `/workspace/<skill-name>`.
2. Include at least:
   - `SKILL.md`
   - `scripts/use.py`
   - `data/input.json`
3. In the same first `exec`, run the script and verify a deterministic marker such as:

   ```text
   SANDBOX_COMPLEX_SKILL_OK sum=10 product=24
   ```

4. Call `register_skill` with `path=/workspace/<skill-name>`.
5. Call `activate` with `skill_name=<skill-name>`.
6. Call `exec` with `workdir=/workspace/.skills/<skill-name>` and run:

   ```bash
   python3 scripts/use.py && echo SANDBOX_ACTIVATED_WRITEBACK_OK > activated_writeback.txt && cat activated_writeback.txt
   ```

7. Require the final answer to contain only an explicit success marker:

   ```text
   E2E_OK:<skill-name>
   ```

Keep the test script robust to working-directory changes. Prefer resolving data paths from `__file__`:

```python
from pathlib import Path
data_path = Path(__file__).resolve().parent.parent / "data" / "input.json"
```

## Success Criteria

The UI should show an assistant final response containing `E2E_OK:<skill-name>`.

Backend logs should show:

- `exec tool invoked`
- `register_skill`
- `activate`
- a second `exec` whose workdir is `/workspace/.skills/<skill-name>`
- `backend=e2b`, `backend=nsjail`, or the expected local backend

After the run, verify the skill store through the UI or API:

- Skill root lists `SKILL.md`, `scripts`, `data`, and `activated_writeback.txt`.
- `scripts/use.py` is readable.
- `data/input.json` is readable.
- `activated_writeback.txt` contains `SANDBOX_ACTIVATED_WRITEBACK_OK`.
- `/api/v1/box/errors` is empty.

## Existing Skill Edit Variant

The base `sandbox-skill-authoring-e2e` case only proves create, register,
activate, and use. To prove that an already activated skill can be modified,
run `sandbox-skill-authoring-edit-existing-e2e` or use its prompt pattern.

The edit variant must include these additional checks:

- The second `exec` uses `workdir=/workspace/.skills/<skill-name>`.
- The second `exec` overwrites `SKILL.md`, `data/input.json`, and
  `scripts/use.py` under the activated skill path.
- The modified script prints a deterministic marker such as:

  ```text
  SANDBOX_SKILL_MODIFIED_OK sum=11 product=56 marker=<updated-marker>
  ```

- `grep -q <updated-marker> SKILL.md scripts/use.py data/input.json` succeeds
  in the same activated-path command.
- Filesystem evidence under the Box-managed skill store shows the updated
  marker, not only the original create marker.

If the model stops after activation and only reruns the original script, treat
that run as a failed edit-existing E2E even when create/register/activate
succeeded.

## Diagnostic Checks

Use these only after the model-driven Debug Chat flow fails:

- `/api/v1/box/status` to confirm backend selection and recent errors.
- `/api/v1/box/sessions` to check leaked or conflicting sessions.
- Direct backend probes to separate provider credentials from LangBot integration.
- Filesystem inspection under the configured Box-managed skill store.

For E2B raw HTTP diagnostics, include a valid template id such as `base`; a missing template can produce schema validation errors that are unrelated to authentication.

## Known Pitfalls

- When Box is available, skills may be owned by the Box runtime and stored in Box-managed skill storage. Do not assume `data/skills` is the active source of truth.
- Public E2B does not provide local bind mounts. Main workspace and activated skill extra mounts must be synchronized into and back out of the E2B sandbox.
- Session metadata should keep LangBot logical paths such as `/workspace`; storing provider-internal paths can make later requests look incompatible.
- nsjail versions differ. Some expose only `--disable_clone_new*` flags and use `--bindmount` instead of `--rw_bind`.
- On WSL, cgroup v2 may exist but not be writable. The backend should warn and fall back to rlimits rather than fail the sandbox.
- If `ALL_PROXY` uses a SOCKS URL and `socksio` is not installed, some Python HTTP clients can fail during startup. Prefer consistent HTTP proxy variables unless SOCKS support is installed.

## Related Troubleshooting

- `sandbox-native-tools-unavailable`
- `e2b-extra-mount-sync-missing`
- `box-session-conflict-logical-metadata`
- `nsjail-cli-compatibility`
- `socks-proxy-without-socksio`

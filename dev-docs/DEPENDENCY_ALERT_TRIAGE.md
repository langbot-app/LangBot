# Dependency alert triage procedure

How to work the Dependabot queue without reporting counts as exploitable
vulnerabilities, and how to close an alert with evidence instead of hope. The
public tracking issue is `langbot-app/LangBot` #2745; this note is the method it
asks maintainers to follow.

## The alert count is not a vulnerability count

A Dependabot alert says a resolved package version falls inside an advisory's
range. It says nothing about whether a reachable code path in LangBot triggers
the bug. Do the reachability step before writing either a fix or a "not
affected" verdict, and record which one you did.

An alert is closed one of three ways, all with a written reason:

| Verdict | Requires |
| --- | --- |
| Fixed | Lock, product floors and every shipped artifact are at or above the patched version, and the normal plus rejection paths still pass |
| Not reachable | The entrypoint, the configuration needed, and the code path that bypasses the vulnerable function |
| Accepted | No patched version exists yet; the exposure window and compensating control are written down |

"Upgraded the lock" alone is not a fix. Alerts are also grouped by *where* the
package is resolved: a stale `plugins/*/uv.lock` is a distinct finding from
`uv.lock` even when the advisory is the same, because the plugin ships its own
resolve.

## Fix the floor, not only the resolve

Raising a version only inside a lock makes the next `uv lock` reintroduce the
advisory. Any dependency that survives a re-resolve needs its constraint raised
in the owning `pyproject.toml` too. Transitive packages are the common case: the
alert names the transitive package, the cap comes from a direct one.

Resolve caps rather than fighting them. `litellm` pinned
`filelock>=3.16.1,<4.0`, so `filelock` advisories could not be cleared until
`litellm` moved to a release with `filelock<5`.

## Evidence to collect

1. The current resolved version and the advisory's vulnerable range, from the
   alert — not from the issue text.
2. Whether LangBot is on the affected side of the API. `webauthn` pulls
   `pyasn1`, so its quadratic-time DER decoding is on the auth path;
   `pypdf` had no importer in `src/` or `plugins/`, which is different evidence.
3. A measurement or a passing test on both the accept and reject path. Quote the
   number; "looks fine" is not evidence.
4. A re-query of the resolved versions in `uv.lock`, `plugins/Runner/uv.lock`,
   `plugins/Runner/LocalAgent/uv.lock` and the frontend locks after the change.

## Frontend locks

`web/package-lock.json`, `web/pnpm-lock.yaml` and `docs/package-lock.json`
resolve separately. Classify each hit by whether it runs in browser code, in a
Node-side adapter, or only in the dev server, and fix the lockfile that actually
ships. Do not describe a dev-server-only advisory as a browser vulnerability.

## Baseline drift

`uv.lock` and the plugin locks drift apart because plugins resolve on their own.
A run that updates one and not the others leaves advisory counts unchanged in
GitHub while looking green locally. Re-query all of them, which is what the
completion evidence in #2745 asks for.

## Review checklist

- [ ] Verdict recorded per alert, from the three above
- [ ] Floor raised in the owning `pyproject.toml`, not only in a lock
- [ ] Every resolved artifact re-queried after the change
- [ ] Accept path and rejection path both exercised
- [ ] Unpublished advisories coordinated in Security Advisories, with only the
      cleared conclusion posted publicly

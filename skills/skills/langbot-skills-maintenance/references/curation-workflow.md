# Curation Workflow

Use this checklist when the repository starts accumulating repeated cases, copied steps, or overlapping troubleshooting entries.

## Audit Pass

1. Inspect the current surface:
   - `bin/lbs case list`
   - `bin/lbs case list --json --priority p0 --automation`
   - `bin/lbs case list --ready`
   - `bin/lbs case list --machine-ready`
   - `bin/lbs suite list`
   - `bin/lbs fixture list`
   - `rg "sandbox|provider|pipeline|plugin|knowledge|mcp" skills`
   - `rg "If .* fails|Known Pitfalls|Debug Chat|/api/v1" skills`
2. Group nearby assets by intent, not by file path:
   - user-facing scenario
   - backend or provider dependency
   - failure signature
   - pass/fail evidence
3. Pick one canonical owner:
   - stable procedures belong in `references/`
   - deterministic files and packages belong in `fixtures/` plus `fixtures/fixtures.json`
   - repeated failure signatures belong in `troubleshooting/`
   - runnable QA paths belong in `cases/`
   - reusable groups of QA paths belong in `suites/`
   - skill entry points belong in `SKILL.md`

## Merge Or Split

Merge when two files share the same trigger, root cause, and fix. Keep the stronger id and move missing patterns into it.

Split when a file mixes unrelated failure modes or requires different fixes. Each troubleshooting id should map to one diagnosis path.

Move repeated step lists out of cases and into a reference when more than one case would need the same prompt, UI path, or log interpretation.

Add or update a suite when developers repeatedly run the same ordered group of cases. Do not copy case steps into suites; use `bin/lbs suite plan <suite-id>` to expand the group.
Use `bin/lbs suite start <suite-id>` and `bin/lbs suite report <suite-id> --evidence-dir <dir>` when validating that a suite is operational end to end.

Add or update `fixtures/fixtures.json` when a case depends on a deterministic file, plugin package, or local test server. The manifest should use repo-relative paths under the owning skill and should not contain machine-local absolute paths.

When adding Debug Chat Playwright automation, reuse `scripts/e2e/lib/debug-chat.mjs` for navigation, prompt send, response leaf matching, and known failure classification. Keep case-specific prompts and expected sentinels in case YAML automation fields when possible.

## Case Review

For every changed case:

1. Ensure `steps` describe what to execute, not every command in the underlying implementation.
2. Ensure `checks` contain observable UI, log, network, or filesystem evidence.
3. Ensure `diagnostics` are fallback investigation hints, not pass criteria.
4. Ensure `priority`, `risk`, `ci_eligible`, and `evidence_required` match the actual repeatability and evidence burden.
5. Put must-have env vars in `env` / `automation_env`; put one-of choices such as URL-or-name in `env_any` / `automation_env_any`.
6. Ensure linked `skills` and `troubleshooting` ids exist.
7. Run:

   ```bash
   bin/lbs validate
   bin/lbs index --check
   bin/lbs index
   bin/lbs test plan <case-id>
   ```

## Final Gate

Before handing off:

- `git diff --stat` should show a focused change set.
- `skills.index.json` should be regenerated only by `bin/lbs index`.
- No new asset should contain local credentials, OAuth tokens, API keys, or copied localStorage values.
- The final note should say which checks ran and which cases or troubleshooting ids changed.

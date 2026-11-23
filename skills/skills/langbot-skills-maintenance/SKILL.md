---
name: langbot-skills-maintenance
description: Maintain the langbot-skills repository with low duplication. Use when adding, editing, or auditing LangBot skills, references, cases, troubleshooting entries, indexes, or periodic entropy-control checks for this skills repository.
---

# LangBot Skills Maintenance

Use this skill before changing reusable assets in this repository.

## Workflow

1. Read `AGENTS.md`, `skills/.env`, and the relevant existing skill files.
2. Classify the change:
   - `SKILL.md` for routing and concise operating rules.
   - `references/*.md` for canonical detailed workflows.
   - `cases/*.yaml` for executable test-plan skeletons.
   - `suites/*.yaml` for reusable groups of case ids.
   - `fixtures/fixtures.json` for deterministic fixture readiness metadata.
   - `reports/evidence/<run-id>/automation-result.json` as automation output and `reports/evidence/<run-id>/result.json` as final judgment output; neither is a catalog asset to commit.
   - `troubleshooting/*.yaml` for one reusable failure mode.
3. Search existing assets before adding new files:
   - `rg "<feature|error|case id>" skills`
   - `bin/lbs case list`
   - `bin/lbs suite list`
   - `bin/lbs fixture list`
4. Put detail in one canonical place and link to it from cases or routing bullets.
5. Run the checks in `AGENTS.md` after edits.

## Entropy Rules

- Prefer extending an existing reference or troubleshooting entry when the root cause is the same.
- Keep cases short: setup, action, evidence, pass/fail checks. Do not paste long prompts or debug transcripts when a reference exists.
- Put machine-checkable inputs in `env`, `automation_env`, or fixtures; put operator-confirmed assumptions in `preconditions` so `test plan` can surface `manual_check`.
- Keep suites short: title, intent, tags, and ordered case ids. Do not duplicate case steps inside a suite.
- Keep fixture manifests factual: id, title, path, kind, and related case ids. Do not encode environment-specific absolute paths.
- Keep troubleshooting entries narrow: symptoms, patterns, likely causes, fixes, related assets.
- Do not hardcode local ports, browser profile paths, secrets, tokens, or provider keys.
- Use `bin/lbs index --check` to verify the committed index is current without writing it; run `bin/lbs index` when the index needs regeneration.

For periodic repository audits, read `references/curation-workflow.md`.

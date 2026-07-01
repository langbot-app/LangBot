# Agent Workflow

This repository stores reusable LangBot agent-testing assets. Keep changes structured so the next agent does not need to rediscover paths.

## First Steps

1. Read `skills/.env` before using local URLs, paths, browser profiles, or proxy defaults. If present, `skills/.env.local` overrides it for this machine and must not be committed. On a new machine, copy `skills/.env.example` to `skills/.env.local` first.
2. Pick the smallest relevant skill:
   - `langbot-env-setup` for environment, browser, OAuth, proxy, and startup.
   - `langbot-testing` for WebUI, provider, pipeline, cases, and troubleshooting.
   - `langbot-skills-maintenance` for adding, deduplicating, or auditing this skills repository.
3. Prefer existing cases and troubleshooting entries before exploring from scratch.

## Editing Rules

- UI/browser testing is the primary QA path. API/curl checks are diagnostic only and cannot make a UI case pass by themselves.
- Put skills under `skills/<name>/`.
- Keep `SKILL.md` concise; move detailed workflows to `references/`.
- Put reusable test paths in `cases/*.yaml`.
- New or edited cases must include `priority`, `risk`, `ci_eligible`, and `evidence_required` so agents can select the right test set without rereading every file.
- Use `env_any` / `automation_env_any` for one-of machine inputs, such as `LANGBOT_PIPELINE_URL|LANGBOT_PIPELINE_NAME`; do not list those alternatives as separate all-required env keys.
- Put reusable groups of cases in `suites/*.yaml` rather than hardcoding test sets in docs or CLI code.
- Put growing failure knowledge in `troubleshooting/*.yaml`.
- Do not hardcode local ports in testing docs; use `skills/.env` variables and machine-local `skills/.env.local` overrides.
- Do not store secrets, API keys, OAuth tokens, or localStorage token values.

## Required Checks

After structural changes, run:

```bash
bin/lbs validate
```

After changing skills, cases, or troubleshooting assets, run:

```bash
bin/lbs index
```

Use `bin/lbs env show` to inspect defaults and `bin/lbs env doctor` when diagnosing local environment readiness. Env output is redacted by default; do not work around that by printing raw secrets.
`bin/lbs` is a generated local wrapper. If it is missing on a fresh checkout, run `npm run bootstrap` from this directory first; `npm install` also regenerates it via `prepare`.
Use `bin/lbs fixture check` before fixture-heavy cases such as MCP, RAG, multimodal, or plugin smoke tests.
Use `bin/lbs case list --ready` for cases that have no missing machine inputs and no manual preconditions. Use `bin/lbs case list --machine-ready` when you want to keep `manual-check` candidates and confirm their preconditions yourself.

Before executing a saved QA path, generate the agent-facing plan:

```bash
bin/lbs test plan <case-id>
```

Read the plan readiness sections before running the browser path. Missing env,
automation env, or fixture readiness means the case is not ready to execute and
should be marked `blocked` or fixed first.
`manual_check` means machine inputs are present but the agent must verify the
declared `preconditions` or `setup` items before executing the UI path. Do not
turn a `manual_check` case into `pass` until those items were checked in the
same run.

Before executing a group of saved QA paths, generate the suite plan:

```bash
bin/lbs suite plan <suite-id>
```

Use `bin/lbs suite start <suite-id>` to create a shared suite run id, suite evidence root, per-case evidence directories, and `suite-start.json`/`suite-start.md` handoff files. Then run `bin/lbs suite report <suite-id> --evidence-dir <dir>` to aggregate case results.
Automation scripts write `automation-result.json`; write the final per-case `result.json` with `bin/lbs test result <case-id> --result <status> --reason <text> --evidence-dir <dir> --evidence <comma-list>` after collecting the required evidence. A `pass` result must include all required evidence.
For runner-specific Debug Chat cases, prefer case-specific pipeline env keys such as `LANGBOT_LOCAL_AGENT_PIPELINE_URL` over the generic `LANGBOT_PIPELINE_URL`; otherwise an agent can accidentally test the wrong runner.

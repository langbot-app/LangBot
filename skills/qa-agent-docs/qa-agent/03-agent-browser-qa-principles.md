# Agent Browser QA Principles

This document fixes the direction of LangBot agent testing so the project does not drift into a backend API smoke-test framework.

## Primary Goal

`langbot-skills` should help an agent behave like a QA engineer using the product, not like a backend curl script.

The primary path is:

```text
developer intent -> lbs test plan -> agent controls browser -> UI result + console + logs -> report/assets
```

## Rules

1. Browser/UI interaction is the source of truth for product QA cases.
2. A backend API or curl response is never enough to mark a UI case passed.
3. API/curl/log checks are allowed as diagnostics after a UI path is attempted or when debugging environment readiness.
4. A case passes only when the user-visible UI result is correct.
5. The agent should inspect browser console/network output when available.
6. If screenshot or vision capability is available, the agent should check for blank pages, overlap, hidden actions, broken layout, and error toasts.
7. If no visual model is available, use DOM/accessibility snapshots and console output instead.
8. New stable UI paths should be added as `cases/*.yaml`.
9. New recurring failure modes should be added as `troubleshooting/*.yaml`.
10. Secrets, tokens, API keys, and localStorage token values must never be printed.

## Command Semantics

`lbs` manages assets and produces plans. It does not replace the agent's browser-control ability.

```bash
bin/lbs test plan pipeline-debug-chat
```

This command outputs:

- environment variables to use
- required skills
- browser steps
- UI/console/visual/log checks
- diagnostic options
- related troubleshooting patterns
- report template

The active agent then executes the plan with Computer Use, Playwright MCP, or another available browser-control tool.

## Diagnostics

Diagnostics can include:

- `bin/lbs env doctor`
- browser console/network inspection
- backend logs
- targeted API/curl checks

Diagnostics answer "where did it fail?" They do not replace "did the user-visible UI work?"

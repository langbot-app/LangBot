# Historical Local-Agent Migration Plan

This document is archived. The official local agent runner now lives in the
separate repository:

```text
/home/glwuy/langbot-app/langbot-local-agent
```

Do not use this file as implementation guidance. The current source of truth is
the local-agent repository README, tests, and the LangBot Runner Protocol v1
docs.

Current Protocol v1 rules:

- Use `ctx.input` for the current event input.
- Do not read `ctx.bootstrap`; Protocol v1 does not inline bootstrap/history
  windows. Use authorized history pull APIs when more context is needed.
- Static runner prompt config may be read from `ctx.config["prompt"]`; effective
  Host-composed prompt data should be pulled through the authorized prompt API.
- Do not rely on top-level `ctx.messages`, `ctx.prompt`, or `ctx.params`.
- Include `ctx.run_id` in every `RunnerResult` factory call.

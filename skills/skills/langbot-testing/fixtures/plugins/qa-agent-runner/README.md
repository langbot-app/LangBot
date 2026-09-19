# QA Runner Fixture

Deterministic Runner plugin source used by `langbot-skills` probes and future browser release-gate cases.

Runner id after installation should be:

```text
plugin:qa/agent-runner/default
```

Expected behavior:

- normal input returns `QA_RUNNER_OK:<input>`
- input containing `stream` emits streaming chunks then completes
- input containing `fail` returns `QA_RUNNER_CONTROLLED_FAILURE`

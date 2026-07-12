# QA Plugin Smoke

Local fixture plugin for LangBot plugin E2E smoke testing.

Tools:

- `qa_echo(text)` returns `qa-plugin-smoke:<text>`.
- `qa_plugin_echo(text)` returns `qa-plugin-smoke:<text>`.
- `qa_plugin_sleep(seconds, text)` waits up to 15 seconds and returns `qa-plugin-smoke:sleep:<seconds>:<text>`.

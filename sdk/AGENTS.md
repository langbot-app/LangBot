# AGENTS.md

This file guides code agents working in the `langbot-plugin-sdk` repository. `CLAUDE.md` is a symlink to this file.

Read `ARCHITECTURE.md` before non-trivial SDK, CLI, Plugin Runtime, Box Runtime, protocol, or cross-repo LangBot changes. This file is the working checklist; `ARCHITECTURE.md` is the system map.

## Quick Facts

- Package name: `langbot-plugin`.
- Python: `>=3.10`.
- CLI entrypoint: `lbp = langbot_plugin.cli:main`.
- Main consumers: LangBot main repo and third-party plugins.
- Runtime license: `src/langbot_plugin/runtime/` is AGPL; the rest is Apache 2.0.
- LangBot pins this package in its `pyproject.toml`; local cross-repo testing needs a local install into LangBot's venv.

## Essential Commands

```bash
uv sync --dev
uv run lbp --help
uv run lbp ver
uv run lbp init MyPlugin
uv run lbp comp Command
uv run lbp run
uv run lbp build
uv run lbp publish
uv run lbp rt
uv run lbp box
```

Focused validation:

```bash
uv run pytest tests/api -q
uv run pytest tests/cli -q
uv run pytest tests/runtime -q
uv run pytest tests/box -q
uv run pytest tests/packaging/test_installed_cli_blackbox.py -q
uv run python scripts/check_action_consistency.py
```

## Where to Look

- Architecture map: `ARCHITECTURE.md`.
- CLI entrypoint and flags: `src/langbot_plugin/cli/__init__.py`.
- Plugin SDK APIs: `src/langbot_plugin/api/`.
- Plugin Runtime: `src/langbot_plugin/runtime/`.
- Box Runtime: `src/langbot_plugin/box/`.
- Action protocol: `src/langbot_plugin/entities/io/` and `src/langbot_plugin/runtime/io/handler.py`.
- Plugin tutorial: https://langbot.app/docs/zh/plugin/dev/tutor.
- Runtime/CLI/SDK debugging: https://langbot.app/docs/zh/develop/plugin-runtime.
- LangBot main repo: `../LangBot/`.

## Cross-Repo LangBot Testing

Use sibling repos:

```text
langbot-projects/
├── LangBot/
└── langbot-plugin-sdk/
```

When changing shared entities, component contracts, action payloads, Plugin Runtime, or Box Runtime:

```bash
# from langbot-plugin-sdk, with LangBot's .venv active
uv pip install .

# from LangBot; keep local SDK installed
uv run --no-sync main.py
```

Standalone runtime flows:

```bash
# Plugin Runtime, default control :5400 and debug :5401
uv run --no-sync lbp rt

# Box Runtime, default :5410
uv run --no-sync lbp box
```

Then configure LangBot as needed:

- Plugin runtime: `plugin.runtime_ws_url: ws://localhost:5400/control/ws`, launch LangBot with `--standalone-runtime`.
- Box runtime: `box.runtime.endpoint: ws://127.0.0.1:5410`, choose `box.backend`, launch LangBot with `--standalone-box`.

## Change Rules

- Treat action enums and Pydantic models as cross-process API contracts; update callers, handlers, and tests together.
- Do not duplicate action strings outside the enum definitions.
- Keep generated plugin templates, component base classes, CLI renderer behavior, and docs consistent when component contracts change.
- Preserve `uv run --no-sync` guidance for local SDK testing; otherwise LangBot may reinstall the pinned PyPI package.
- Keep comments/docstrings in English and user-facing labels/descriptions i18n-ready.
- Commit message format: `<type>(<scope>): <subject>`.

## Runtime Pitfalls

- Direct local LangBot runs often spawn Plugin Runtime over stdio; stdio disconnects cannot auto-reconnect.
- Orphan Runtime processes holding `5400`/`5401` commonly break `lbp run` debugging.
- Docker deployments use `langbot_plugin_runtime:5400/control/ws` and `langbot_box:5410` as service hosts.
- A false Box “no backend” often means Docker socket permission is missing, not that Docker is unavailable.
- nsjail inside containers needs host cgroup namespace for cgroup v2 limits; do not fake memory limits with `RLIMIT_AS` because it breaks tools that reserve large virtual memory.
- There is no supported `python -m langbot_plugin.box` entrypoint; use `lbp box`.
- `CLAUDE.md` is a symlink to this file; edit `AGENTS.md`, not the symlink.

## Principles

- Keep it simple, stupid.
- Entities should not be multiplied unnecessarily.
- 八荣八耻

    以瞎猜接口为耻，以认真查询为荣。
    以模糊执行为耻，以寻求确认为荣。
    以臆想业务为耻，以人类确认为荣。
    以创造接口为耻，以复用现有为荣。
    以跳过验证为耻，以主动测试为荣。
    以破坏架构为耻，以遵循规范为荣。
    以假装理解为耻，以诚实无知为荣。
    以盲目修改为耻，以谨慎重构为荣。

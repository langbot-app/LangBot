# LangBot fnOS Packaging

This directory packages LangBot as a `.fpk` app for the fnOS App Store. It is a native deployment: no Docker involved — uv creates a Python virtual environment directly on the NAS, and Node.js v22 from the fnOS App Store provides the Box sandbox and npx MCP capabilities.

## Directory Structure

```
packaging/fnos/
├── manifest                    # App metadata (appname/version/port/dependency declarations)
├── build.sh                    # One-shot build script (shared by local and CI)
├── LICENSE
├── config/
│   ├── privilege               # Privilege config (run-as: root)
│   └── resource                # Persistent data share declaration (langbot/data)
├── cmd/                        # Lifecycle scripts (fnOS invokes them with TRIM_* env vars)
│   ├── main                    # Service start/stop manager (start/stop/status, owns PID/log)
│   ├── install_init            # Pre-install hook
│   ├── install_callback        # Post-install hook: create venv, uv sync deps, seed config.yaml port
│   ├── upgrade_init            # Pre-upgrade hook
│   ├── upgrade_callback        # Post-upgrade hook
│   ├── uninstall_init         # Pre-uninstall hook
│   ├── uninstall_callback      # Post-uninstall hook (keeps data per wizard choice)
│   ├── config_init             # Pre-config-change hook
│   └── config_callback         # Post-config-change hook (apply new port etc.)
├── wizard/                     # Install wizards (JSON forms; values passed as wizard_* env vars)
│   ├── install                 # On install: Node version, web port, deployment-time notice
│   ├── upgrade                 # On upgrade: Node version confirmation
│   └── uninstall               # On uninstall: whether to keep data
├── app/
│   ├── ui/config               # Desktop entry declaration (${wizard_port} placeholder, substituted by fnOS at install)
│   ├── desktop/langbot.main.url
│   ├── langbot/                # [generated] repo source synced via rsync (includes web/dist)
│   └── bin/                    # [generated] offline uv binaries (x86_64/aarch64)
├── ICON.PNG / ICON_256.PNG     # [generated] derived from res/logo-blue.png
└── langbot.fpk                 # [generated] final artifact
```

Paths marked `[generated]` are produced by `build.sh`, ignored via `.gitignore`; everything else is a git-tracked source file.

## Building

### Locally

```bash
bash packaging/fnos/build.sh
```

Dependencies: python3 + Pillow, node + npm (or pnpm), fnpack (official fnOS packaging CLI, download from https://developer.fnnas.com/docs/cli/fnpack).

The version comes from `version=` maintained in the manifest; it can also be injected: `FPK_VERSION=4.10.10-1 bash packaging/fnos/build.sh`.

### CI

[`.github/workflows/build-fnos-fpk.yaml`](../../.github/workflows/build-fnos-fpk.yaml) triggers automatically on Release publication and uploads `langbot-<version>-fnos.fpk` to the Release; it can also be triggered manually via workflow_dispatch.

Version sources (consistent with the other release workflows):

| Trigger | Version source |
|---|---|
| Release/tag auto build | Tag name (`v4.10.10-1` → in-package `4.10.10-1`; build.sh strips the `v` prefix on injection) |
| Manual workflow_dispatch / local build | Version maintained in manifest |

## Final Artifact

`langbot.fpk` (gzip + tar archive), containing:

- `manifest` — realigned and appended with a `checksum` field by fnpack
- `app.tgz` — app payload (source, web/dist, uv binaries, entry configs)
- `cmd/`, `config/`, `wizard/` — lifecycle scripts and wizards
- `ICON.PNG`, `ICON_256.PNG`, `LICENSE`

The first startup after installation takes about 5-10 minutes to finish dependency deployment (uv venv + sync); after that the web admin UI is reachable via the desktop icon or `http://<NAS-IP>:<port>` (default port 5300).

## References

- fnOS developer docs: https://developer.fnnas.com/
- fnOS app wizard: https://developer.fnnas.com/docs/core-concepts/wizard/
- fnpack CLI: https://developer.fnnas.com/docs/cli/fnpack

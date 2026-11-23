---
name: langbot-env-setup
description: Prepare a local LangBot development and testing environment for an AI agent. Use when setting up WSL or Linux development, shared local URL variables, proxy variables, backend/frontend startup, Playwright MCP browser access, GitHub OAuth browser login, persisted Chrome profiles, or future Codex computer-use environment paths.
---

# LangBot Environment Setup

Use this skill when a task needs LangBot to be in a testable state before product testing or development verification.

## Routing

- **Shared local variables**: read `../.env` before using URL, path, browser profile, or proxy defaults.
- **Always start here**: read `references/browser-access-selection.md` to choose the browser-control path.
- **LangBot service checks and startup**: read `references/service-startup.md`.
- **Computer Use available**: read `references/computer-use.md`. This path usually needs less browser/MCP setup.
- **No Computer Use, browser automation required**: read `references/playwright-mcp.md`.
- **GitHub OAuth or persisted login profile**: read `references/oauth-browser-profile.md`.
- **WSL-specific notes**: read `references/wsl-notes.md` only when running under WSL.
- **Proxy setup**: read `references/proxy.md` when external login, model provider tests, or package downloads time out.
- **Headless-only automation**: use only after a profile already contains a valid LangBot login. Do not ask the agent to enter GitHub credentials or 2FA.

## Rules

- Never handle the user's GitHub password, passkey, recovery code, or 2FA secret.
- For OAuth login, open a visible browser and let the user complete the credential steps.
- Reuse a fixed browser profile path so the agent can later access the logged-in LangBot session.
- Keep environment-specific paths and commands in `references/`, not in this file.
- Treat environment setup as complete only after the target LangBot services are reachable and the browser profile can access the WebUI.

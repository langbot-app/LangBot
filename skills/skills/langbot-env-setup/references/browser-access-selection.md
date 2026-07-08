# Browser Access Selection

Choose the lightest browser-control path that can complete the task.

## Decision Order

1. If Codex Computer Use, Claude Computer Use, or another visible browser-control tool is available, use `computer-use.md`.
2. If no computer-control tool is available but Playwright MCP is available, use `playwright-mcp.md`.
3. If the browser session must survive restarts or OAuth login is required, also use `oauth-browser-profile.md`.
4. If running under WSL, add `wsl-notes.md`.
5. If external sites or model providers time out, add `proxy.md`.

## Principle

Computer Use and Playwright MCP are alternative browser-control paths. Both still need LangBot services to be reachable, so service checks stay in `service-startup.md`.

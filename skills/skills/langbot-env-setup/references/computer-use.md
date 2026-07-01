# Computer Use Browser Path

Use this path when Codex Computer Use, Claude Computer Use, or another agent-visible browser-control capability is available.

## Why This Path Is Simpler

Computer Use can interact with a visible browser directly, so it usually does not need Playwright MCP configuration or a separate MCP browser bridge.

## Workflow

1. Verify LangBot backend/frontend with `service-startup.md`.
2. Open the WebUI in the controlled browser.
3. If login is needed, let the user complete GitHub OAuth. Never handle credentials or 2FA.
4. Keep the browser/profile available for later testing.
5. Hand off to `langbot-testing` after the page shows the logged-in WebUI.

## Still Required

- Proxy may still be needed for GitHub OAuth or model provider tests. Use `proxy.md`.
- Persisted profile details may still matter if the computer-control browser is restarted. Use `oauth-browser-profile.md` if login state must survive.

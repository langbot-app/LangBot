# Playwright MCP Browser Path

Use this path when the agent needs browser automation but no Computer Use browser-control path is available.

## Known Paths

- Persistent browser profile: `LANGBOT_BROWSER_PROFILE` from `skills/.env.local`
- Chromium executable: `LANGBOT_CHROMIUM_EXECUTABLE` from `skills/.env.local`
- Codex MCP config: `$CODEX_HOME/config.toml` or the config path used by the active agent.

## MCP Config

Keep the profile path fixed so the agent can reuse authenticated state.

```toml
[mcp_servers.playwright]
command = "npx"
args = ["-y", "@playwright/mcp@latest", "--no-sandbox", "--executable-path", "<LANGBOT_CHROMIUM_EXECUTABLE>", "--proxy-server", "<LANGBOT_PROXY_SOCKS>", "--proxy-bypass", "localhost,127.0.0.1", "--user-data-dir", "<LANGBOT_BROWSER_PROFILE>"]
```

After changing MCP config, restart Codex so the MCP server is relaunched with the new args.

## Visible Login

For OAuth login, Playwright MCP's headless browser is not enough. Launch a visible browser with the same profile and let the user complete login. Use `oauth-browser-profile.md`.

## Common Failures

- MCP still uses old args after editing config: restart Codex or kill old `playwright-mcp` processes and restart the session.
- Browser is headless during OAuth: use the visible login command from `oauth-browser-profile.md`.

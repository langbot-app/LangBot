# OAuth Browser Profile

Use this reference when LangBot or LangBot Space needs GitHub OAuth login and the agent must reuse the authenticated browser state later.

Read `skills/.env` first for `LANGBOT_BACKEND_URL`, `LANGBOT_FRONTEND_URL`, `LANGBOT_BROWSER_PROFILE`, `LANGBOT_CHROMIUM_EXECUTABLE`, and proxy defaults.

## Rules

- Never handle the user's GitHub password, passkey, recovery code, or 2FA secret.
- Open a visible browser and let the user complete credential steps.
- Reuse a fixed browser profile path.
- Do not print token values. It is acceptable to report localStorage key names.

## Manual Visible Login Flow

1. Verify LangBot backend is reachable with `service-startup.md`.
2. Launch a visible Chromium window with the persistent profile:

```bash
setsid "$LANGBOT_CHROMIUM_EXECUTABLE" \
  --no-sandbox \
  --ozone-platform=x11 \
  --user-data-dir="$LANGBOT_BROWSER_PROFILE" \
  --proxy-server="$LANGBOT_PROXY_SOCKS" \
  --proxy-bypass-list="$LANGBOT_NO_PROXY" \
  "$LANGBOT_BACKEND_URL/login" \
  >/tmp/langbot-visible-chrome.log 2>&1 < /dev/null &
```

3. The user completes:

```text
Login with Space -> Login with GitHub -> GitHub credentials / 2FA -> authorize
```

4. The agent can then reuse the same profile for automated checks.

## Expected Successful State

After login, LangBot should redirect away from `/login`, for example to a `/home/...` URL on the selected origin.

Expected visible signals:

```text
LangBot
Dashboard
Home
Bots
Pipelines
Knowledge
Extensions
```

Expected localStorage key names:

```text
token
userEmail
langbot_language
```

If the user logged in on one origin but `LANGBOT_FRONTEND_URL` still shows `/login`, copy only the auth state needed between origins. Do not print token values.

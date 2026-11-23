# WSL Notes

Use this reference only for WSL-specific details. Do not put generic LangBot startup or browser-login steps here.

## Network

GitHub login and model provider calls may require proxy access from WSL.

Working proxy form:

```bash
socks5://127.0.0.1:7890
```

Bypass local LangBot:

```bash
localhost,127.0.0.1
```

Quick checks:

```bash
curl -I --max-time 8 --proxy socks5h://127.0.0.1:7890 https://github.com
curl -I --max-time 3 "$LANGBOT_BACKEND_URL"
```

## Visible Browser

If OAuth requires a visible browser, WSL must have a usable display path. If a visible Chromium launch fails, check the local WSL GUI/X11 setup before changing LangBot config.

## Common Failures

- `ERR_NETWORK_CHANGED` or GitHub timeout: browser is not using the SOCKS proxy.
- LangBot connection refused: backend is not running or not reachable from WSL.
- User cannot type credentials: browser is headless or not visible to the user.

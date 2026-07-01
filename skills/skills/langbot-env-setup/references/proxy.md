# Proxy Setup

Use this reference when GitHub OAuth, package installation, model provider tests, or external API calls time out.

Read defaults from `skills/.env` first.

## Standard Local Proxy

```bash
export HTTP_PROXY="$LANGBOT_PROXY_HTTP"
export HTTPS_PROXY="$LANGBOT_PROXY_HTTP"
export ALL_PROXY="$LANGBOT_PROXY_SOCKS"
export http_proxy="$LANGBOT_PROXY_HTTP"
export https_proxy="$LANGBOT_PROXY_HTTP"
export all_proxy="$LANGBOT_PROXY_SOCKS"
export NO_PROXY="$LANGBOT_NO_PROXY"
export no_proxy="$LANGBOT_NO_PROXY"
```

## Rule

Keep uppercase and lowercase proxy variables consistent. Different libraries read different names.

## Checks

```bash
env | rg -i '^(http|https|all|no)_?proxy='
curl -I --max-time 8 --proxy "$LANGBOT_PROXY_SOCKS" https://github.com
curl -I --max-time 3 "$LANGBOT_BACKEND_URL"
```

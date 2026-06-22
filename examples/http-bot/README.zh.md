# HTTP Bot 适配器 —— 参考客户端

> [English](./README.md) | 中文

面向 LangBot **HTTP Bot** 平台适配器的极简、低依赖客户端示例。
它们完整展示了整条链路:对请求签名、推送一条消息、在回调端点接收
1→M 的多段回复。

完整指南:[`docs/platforms/http-bot.md`](../../docs/platforms/http-bot.md)。
机器可读的接口契约:[`docs/http-bot-openapi.json`](../../docs/http-bot-openapi.json)。

## 文件清单

| 文件 | 是什么 |
|---|---|
| `playground.py` | **浏览器交互式调试台** —— 单文件 Web 应用,在浏览器里和一个运行中的 `http_bot` bot 对话,实时观察签名 / 202 / 回调。零额外依赖。 |
| `client.py` | Python 客户端 + Flask 回调接收端(`pip install flask requests`)。 |
| `client.ts` | TypeScript/Node 18+ 客户端 + 回调接收端,**零依赖**(`npx tsx client.ts`)。 |

三者实现完全一致的 HMAC-SHA256 签名方案
(`sha256=hex(HMAC(secret, "{timestamp}." + body))`)—— 已与适配器逐字节比对验证。

## 交互式 playground(推荐先跑这个)

一个自包含的 Web 控制台:在浏览器里输入消息,它会被签名并 POST 给一个
**运行中**的 `http_bot` bot,bot 的回复会流式回到页面上 —— 调试面板会显示
签名、`202` 确认,以及每条回调的 `sequence` / 签名验证结果。

```bash
# 在 LangBot 仓库根目录、后端已启动的前提下:
PUBLIC_IP=<你的主机IP> ./.venv/bin/python examples/http-bot/playground.py
# 然后打开  http://<你的主机IP>:8920/
```

启动时它会从 `data/langbot.db` 读取 LangBot API key 和 `http_bot` bot,
并通过 LangBot API 把该 bot 配好(入站/出站密钥 + `callback_url`)指回自己 ——
bot 会热加载,无需重启。前提:有一个已启用、绑定了可用 pipeline 的
`http_bot` bot,且端口 `8920` 能从你的浏览器访问到。

可调环境变量:`PUBLIC_IP`(默认 `127.0.0.1`)、`PLAYGROUND_PORT`(默认 `8920`)。

## 无头客户端

```bash
# Python —— 终端 1:回调接收端(你的 callback_url 指向它)
python client.py serve --port 8900 --secret SHARED_SECRET

# Python —— 终端 2:推送一条消息
python client.py push --url https://your-langbot/bots/<BOT_UUID> \
    --secret SHARED_SECRET --session ticket-1 --text "hello"

# 阻塞式同步模式
python client.py sync  --url https://your-langbot/bots/<BOT_UUID> \
    --secret SHARED_SECRET --session ticket-1 --text "hello"

# 重置一个会话
python client.py reset --url https://your-langbot/bots/<BOT_UUID> \
    --secret SHARED_SECRET --session ticket-1
```

```bash
# TypeScript(Node 18+)
npx tsx client.ts serve 8900 SHARED_SECRET
npx tsx client.ts push  https://your-langbot/bots/<BOT_UUID> SHARED_SECRET ticket-1 "hello"
```

当 bot 回复时,接收端会逐条打印,带上各自的 `sequence`,并在最后一条标记
`[FINAL]` —— 这就是 1→M 多段回复模型的实际效果。

> bot 的 `callback_url` 必须能从 LangBot 访问到。本地测试时,可用隧道
> (cloudflared / ngrok)把你的接收端暴露出去,并把那个 URL 填进 bot 配置。

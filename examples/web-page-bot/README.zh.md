# 页面机器人适配器 —— 嵌入演示

> [English](./README.md) | 中文

一个自包含的单文件 HTML 页面，用于演示 LangBot **页面机器人**
(`web_page_bot`) 的可嵌入聊天组件 —— 也就是你用一行 `<script>` 标签就能放到任意
网站上的那个组件。

完整指南：[docs.langbot.app —— 页面机器人](https://docs.langbot.app/zh/usage/platforms/webpage)。

## 文件清单

| 文件 | 是什么 |
|---|---|
| `index.html` | **浏览器演示页** —— 打开它，填上一个运行中的 LangBot 实例地址 + 你创建的页面机器人，它就会加载真实的嵌入组件，让你像网站访客一样和机器人对话。零依赖，无需构建。 |

## 使用方法

1. 在 LangBot WebUI 中，用 **页面机器人**（`web_page_bot`）适配器创建一个机器人，
   并绑定一个可用的流水线。从生成的嵌入代码里复制它的 **机器人 UUID**。
2. 在浏览器中打开 `index.html`，以下任一方式皆可：
   - 直接双击该文件；或
   - 起一个静态服务：`python3 -m http.server 8930`，然后打开
     `http://localhost:8930/examples/web-page-bot/`。
3. 填写：
   - **LangBot base URL** —— 你的实例在该浏览器中可访问的地址
     （例如 `http://localhost:5300`，或你的公网地址）。
   - **页面机器人 UUID** —— 第 1 步里复制的。
   - **组件标题** —— 可选，对应 `data-title` 属性。
4. 点击 **Load widget**。页面右下角会出现一个浮动聊天气泡 —— 点开即可对话。

页面还会实时渲染出你需要粘贴到自己网站（放在 `</body>` 前）的那段 `<script>`
代码，并随着你编辑输入框同步更新。

## 它演示了什么

- 嵌入契约：`<script data-title="…" src="<base>/api/v1/embed/<uuid>/widget.js"></script>`。
- `widget.js` 由 LangBot 针对该机器人 UUID 预配置后下发 —— 标题、气泡图标、语言
  以及可选的 Cloudflare Turnstile 防护，全部来自机器人配置，无需改动页面。
- 消息通过 WebSocket 发往机器人绑定的流水线，回复流式回到气泡中。

> 组件会从你的 LangBot 实例加载 `widget.js`，因此 **base URL 必须能从你打开本页
> 的浏览器访问到**。如果 LangBot 部署在服务器上，请用它的公网地址而非
> `localhost`。

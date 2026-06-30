<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://www.producthunt.com/products/langbot/launches/langbot?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-langbot" target="_blank" rel="noopener noreferrer"><img alt="LangBot - Easy-to-use global IM bot platform designed for the LLM era | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=979554&amp;theme=light&amp;t=1782822143403"></a>

<h3>Production-grade platform for building agentic IM bots.</h3>
<h4>Quickly build, debug, and ship AI bots to Slack, Discord, Telegram, WeChat, and more.</h4>

English / [简体中文](README_CN.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)

<a href="https://langbot.app">Website</a> ｜
<a href="https://link.langbot.app/en/docs/features">Features</a> ｜
<a href="https://link.langbot.app/en/docs/guide">Docs</a> ｜
<a href="https://link.langbot.app/en/docs/api">API</a> ｜
<a href="https://space.langbot.app/cloud">Cloud</a> ｜
<a href="https://space.langbot.app">Plugin Market</a> ｜
<a href="https://langbot.featurebase.app/roadmap">Roadmap</a>

</div>

</p>

---

## What is LangBot?

LangBot is an **open-source, production-grade platform** for building AI-powered instant messaging bots. It connects Large Language Models (LLMs) to any chat platform, enabling you to create intelligent agents that can converse, execute tasks, and integrate with your existing workflows.

<p align="center">
<img src="res/dashboard-overview.png" alt="LangBot web management dashboard — real-time monitoring of message volume, model calls, success rate and active sessions" width="720"/>
</p>

### Key Capabilities

- **AI Conversations & Agents** — Multi-turn dialogues, tool calling, multi-modal support, streaming output. Built-in RAG (knowledge base) with deep integration to [Dify](https://dify.ai), [Coze](https://coze.com), [n8n](https://n8n.io), [Langflow](https://langflow.org), [Deerflow](https://deerflow.tech), [Weknora](https://weknora.weixin.qq.com).
- **Universal IM Platform Support** — One codebase for Discord, Telegram, Slack, LINE, QQ, WeChat, WeCom, Lark, DingTalk, KOOK.
- **Production-Ready** — Access control, rate limiting, sensitive word filtering, comprehensive monitoring, and exception handling. Trusted by enterprises.
- **Plugin Ecosystem** — Hundreds of plugins, event-driven architecture, component extensions, and [MCP protocol](https://modelcontextprotocol.io/) support.
- **Web Management Panel** — Configure, manage, and monitor your bots through an intuitive browser interface. No YAML editing required.
- **Multi-Pipeline Architecture** — Different bots for different scenarios, with comprehensive monitoring and exception handling.

[→ Learn more about all features](https://link.langbot.app/en/docs/features)

📍 Practical guides: [deploy a multi-platform AI bot in 5 minutes](https://blog.langbot.app/en/blog/deploy-ai-bot-in-5-minutes/), [connect DeepSeek to WeChat, Discord, and Telegram](https://blog.langbot.app/en/blog/connect-deepseek-to-wechat/), [run a Dify Agent in Discord, Telegram, and Slack](https://blog.langbot.app/en/blog/dify-agent-discord-telegram-slack/), and [build an n8n-powered chatbot](https://blog.langbot.app/en/blog/n8n-multi-platform-ai-chatbot/).

---

## 😎 Stay Updated

Click the Star and Watch buttons in the top-right corner of the repository to get the latest updates.

![star gif](https://langbot.app/star.gif)

## Quick Start

### ☁️ LangBot Cloud (Recommended)

**[LangBot Cloud](https://space.langbot.app/cloud)** — Zero deployment, ready to use.

### One-Line Launch

```bash
uvx langbot
```

> Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Visit http://localhost:5300 — done.

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose --profile all up -d
```

### One-Click Cloud Deploy

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**More options:** [Docker](https://link.langbot.app/en/docs/docker) · [Manual](https://link.langbot.app/en/docs/manual-deploy) · [BTPanel](https://link.langbot.app/en/docs/bt-panel) · [Kubernetes](https://docs.langbot.app/en/deploy/langbot/kubernetes)

---

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Discord | ✅ | Official |
| Telegram | ✅ | Official |
| Slack | ✅ | Official |
| LINE | ✅ | Official |
| QQ | ✅ | Personal & Official API (Channel, DM, Group) |
| WeCom | ✅ | Enterprise WeChat, External CS, AI Bot |
| WeChat | ✅ | Personal & Official Account |
| Lark | ✅ | Official |
| DingTalk | ✅ | Official |
| KOOK | ✅ | Official |
| Satori | ✅ |  |
| Email | ✅ | Matrix, Satori |
| Matrix | ✅ | Supports multiple bridged platforms such as Signal, WhatsApp, Messenger, iMessage, Mattermost, Google Chat, IRC, XMPP, Zulip, and more |

---

## Supported LLMs & Integrations

| Provider                                                                                                          | Type         | Status |
| ----------------------------------------------------------------------------------------------------------------- | ------------ | ------ |
| [OpenAI](https://platform.openai.com/)                                                                            | LLM          | ✅     |
| [Anthropic](https://www.anthropic.com/)                                                                           | LLM          | ✅     |
| [DeepSeek](https://www.deepseek.com/)                                                                             | LLM          | ✅     |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat)                                                     | LLM          | ✅     |
| [xAI](https://x.ai/)                                                                                              | LLM          | ✅     |
| [Moonshot](https://www.moonshot.cn/)                                                                              | LLM          | ✅     |
| [Zhipu AI](https://open.bigmodel.cn/)                                                                             | LLM          | ✅     |
| [Ollama](https://ollama.com/)                                                                                     | Local LLM    | ✅     |
| [LM Studio](https://lmstudio.ai/)                                                                                 | Local LLM    | ✅     |
| [Dify](https://dify.ai)                                                                                           | LLMOps       | ✅     |
| [MCP](https://modelcontextprotocol.io/)                                                                           | Protocol     | ✅     |
| [SiliconFlow](https://siliconflow.cn/)                                                                            | Gateway      | ✅     |
| [Aliyun Bailian](https://bailian.console.aliyun.com/)                                                             | Gateway      | ✅     |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | Gateway      | ✅     |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro)                                        | Gateway      | ✅     |
| [GiteeAI](https://ai.gitee.com/)                                                                                  | Gateway      | ✅     |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot)                                                     | GPU Platform | ✅     |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot)                             | GPU Platform | ✅     |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758)                                                    | GPU Platform | ✅     |
| [接口 AI](https://jiekou.ai/)                                                                                     | Gateway      | ✅     |
| [302.AI](https://share.302ai.cn/SuTG99)                                                                             | Gateway      | ✅     |
| [Qiniu](https://www.qiniu.com/ai/agent)                                                                           | Gateway      | ✅     |

[→ View all integrations](https://link.langbot.app/en/docs/features)

---

## Why LangBot?

| Use Case                    | How LangBot Helps                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| **Customer Support**        | Deploy AI agents to Slack/Discord/Telegram that answer questions using your knowledge base |
| **Internal Tools**          | Connect n8n/Dify workflows to WeCom/DingTalk for automated business processes              |
| **Community Management**    | Moderate QQ/Discord groups with AI-powered content filtering and interaction               |
| **Multi-Platform Presence** | One bot, all platforms. Manage from a single dashboard                                     |

---

## Built for AI Agents 🤖

LangBot is **agent-friendly by design** — your coding agents (Claude Code, Codex, Copilot, Cursor, …) can operate, extend, and deploy LangBot with first-class support:

- **MCP Server** — LangBot exposes a built-in [Model Context Protocol](https://modelcontextprotocol.io/) endpoint at `/mcp`, mirroring the HTTP API so an agent can manage bots, pipelines, plugins, and models programmatically. Authenticate with the same API key (set a global key in `config.yaml` or use a per-user key) — no login flow required. Configure it in the Web panel's **API & MCP** tab.
- **In-repo Skills** — The [`skills/`](skills/) directory is the **single source of truth** for working with LangBot: plugin development, core development, end-to-end testing, deployment, and operating the LangBot / LangBot Space MCP servers. Point your agent at this directory and it knows how to build.
- **AGENTS.md** — Every repo ships an [`AGENTS.md`](AGENTS.md) (symlinked to `CLAUDE.md`) describing architecture, conventions, and the rule that API changes must keep the MCP server and skills in sync.
- **`llms.txt`** — Machine-readable project context for LLMs is published on the website.

> **Cloud / Marketplace:** [LangBot Space](https://space.langbot.app) also exposes an MCP server so agents can search and inspect the plugin / MCP / skill marketplace, authenticated with a Personal Access Token.

---

## Live Demo

**Try it now:** https://demo.langbot.dev/

- Email: `demo@langbot.app`
- Password: `langbot123456`

_Note: Public demo environment. Do not enter sensitive information._

---

## Community

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)

- [Discord Community](https://discord.gg/wdNEHETs87)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=langbot-app/LangBot&type=Date)](https://star-history.com/#langbot-app/LangBot&Date)

---

## Contributors

Thanks to all [contributors](https://github.com/langbot-app/LangBot/graphs/contributors) who have helped make LangBot better:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

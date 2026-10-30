<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://hellogithub.com/repository/langbot-app/LangBot" target="_blank"><img src="https://abroad.hellogithub.com/v1/widgets/recommend.svg?rid=5ce8ae2aa4f74316bf393b57b952433c&claim_uid=gtmc6YWjMZkT21R" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>

<h3>让 AI 机器人替你服务社群、客户和团队。</h3>
<h4>用现成场景，或接入你的 Dify / n8n / Coze 应用，在 QQ、微信、企业微信、飞书、钉钉、Discord、Telegram 等平台上稳定运行。</h4>

[English](README.md) / 简体中文 / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-1030838208-blue)](https://qm.qq.com/q/IrlV8QFacU)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)
[![star](https://gitcode.com/RockChinQ/LangBot/star/badge.svg)](https://gitcode.com/RockChinQ/LangBot)

<a href="https://langbot.app">官网</a> ｜
<a href="https://langbot.app/docs/zh/insight/features">特性</a> ｜
<a href="https://langbot.app/docs/zh/insight/guide">文档</a> ｜
<a href="https://langbot.app/docs/zh/tags/readme">API</a> ｜
<a href="https://cloud.langbot.app">Cloud</a> ｜
<a href="https://space.langbot.app">扩展市场</a> ｜
<a href="https://langbot.featurebase.app/roadmap">路线图</a>

</div>

</p>

---

LangBot 是一个**开源的 IM 机器人平台**，专为“一个机器人服务很多人”的场景设计：QQ 群和社区、微信私域、企业微信客服、飞书 / 钉钉内部助手。你可以从现成的场景开始，也可以把已经在 Dify、n8n、Coze 上做好的 AI 应用直接接进聊天平台。多个群、多个平台在同一个面板里管理，出问题时有日志可查。

<p align="center">
<img src="res/dashboard-overview.png" alt="LangBot Web 管理面板仪表盘 — 实时监控消息量、模型调用、成功率与活跃会话" width="720"/>
</p>

### 核心能力

- **一个机器人，覆盖所有群和平台** — QQ、微信、企业微信、飞书、钉钉、Discord、Telegram、Slack、LINE、KOOK 等。不同的群和场景使用不同的机器人与流水线，统一管理。
- **为群聊和客服设计** — 群内触发规则、会话隔离、限速、敏感词过滤、新成员欢迎、好友申请处理，并可通过插件转人工。
- **AI 对话与 Agent** — 多轮对话、工具调用、多模态、流式输出。自带 RAG（知识库），深度集成 [Dify](https://dify.ai)、[Coze](https://coze.com)、[n8n](https://n8n.io)、[Langflow](https://langflow.org)、[Deerflow](https://deerflow.tech)、[Weknora](https://weknora.weixin.qq.com)等 LLMOps 平台。
- **稳定运行，可排查** — 访问控制、全链路日志、调用记录、异常处理与数据导出，服务多个生产环境。
- **插件生态** — 数百个插件、MCP 服务与 Skills，在扩展市场一键安装；事件驱动架构，支持组件扩展。
- **Web 管理面板** — 通过浏览器直观地配置、管理和监控机器人，无需手动编辑配置文件。

[→ 了解更多功能特性](https://langbot.app/docs/zh/insight/features)

📍 实践指南：[5 分钟部署多平台 AI 机器人](https://langbot.app/zh/blog/deploy-ai-bot-in-5-minutes/)、[将 DeepSeek 接入微信、企业微信与 Discord](https://langbot.app/zh/blog/connect-deepseek-to-wechat/)、[让 Dify Agent 跑在 Discord、Telegram 和 Slack 上](https://langbot.app/zh/blog/dify-agent-discord-telegram-slack/)，以及[用 n8n 构建多平台 AI 聊天机器人](https://langbot.app/zh/blog/n8n-multi-platform-ai-chatbot/)。

---

## 😎 保持更新

点击[仓库首页](https://github.com/langbot-app/LangBot)右上角 Star 和 Watch 按钮，获取最新动态。

![star gif](https://langbot.app/star.gif)

## 快速开始

官方插件源码索引：[plugins/README.md](plugins/README.md) · [机器可读目录](plugins/catalog.json) · [插件独立上架流程](plugins/RELEASING.md)。插件保持独立安装，不随 Core 发版打包。

### ☁️ LangBot Cloud（推荐）

[![Deploy on LangBot Cloud](res/langbot-cloud.svg)](https://cloud.langbot.app)

[cloud.langbot.app](https://cloud.langbot.app)

免部署，开箱即用。

### 一键启动

```bash
uvx langbot
```

> 需要安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。访问 http://localhost:5300 即可使用。

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose --profile all up -d
```


### 一键云部署

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**更多方式：** [Docker](https://langbot.app/docs/zh/deploy/langbot/docker) · [手动部署](https://langbot.app/docs/zh/deploy/langbot/manual) · [宝塔面板](https://langbot.app/docs/zh/deploy/langbot/one-click/bt) · [Kubernetes](https://langbot.app/docs/zh/deploy/langbot/kubernetes)

---

## 支持的平台

| 平台 | 状态 | 备注 |
|------|------|------|
| QQ | ✅ | 个人号、官方机器人（频道、私聊、群聊） |
| 微信 | ✅ | 个人微信、微信公众号 |
| 企业微信 | ✅ | 应用消息、对外客服、智能机器人 |
| 飞书 | ✅ | 官方 |
| 钉钉 | ✅ | 官方 |
| Satori | ✅ |  |
| Discord | ✅ | 官方 |
| Telegram | ✅ | 官方 |
| Slack | ✅ | 官方 |
| LINE | ✅ | 官方 |
| KOOK | ✅ | 官方 |
| Email | ✅ | 只 Matrix、Satori |
| Matrix | ✅ | 支持多种桥接平台，如 Signal、WhatsApp、Messenger、iMessage、Mattermost、Google Chat、IRC、XMPP、Zulip 等 |

---

## 支持的大模型与集成

| 提供商 | 类型 | 状态 |
|--------|------|------|
| [OpenAI](https://platform.openai.com/) | LLM | ✅ |
| [Anthropic](https://www.anthropic.com/) | LLM | ✅ |
| [DeepSeek](https://www.deepseek.com/) | LLM | ✅ |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | LLM | ✅ |
| [xAI](https://x.ai/) | LLM | ✅ |
| [Moonshot](https://www.moonshot.cn/) | LLM | ✅ |
| [智谱AI](https://open.bigmodel.cn/) | LLM | ✅ |
| [Ollama](https://ollama.com/) | 本地 LLM | ✅ |
| [LM Studio](https://lmstudio.ai/) | 本地 LLM | ✅ |
| [Dify](https://dify.ai) | LLMOps | ✅ |
| [MCP](https://modelcontextprotocol.io/) | 协议 | ✅ |
| [SiliconFlow](https://siliconflow.cn/) | 聚合平台 | ✅ |
| [阿里云百炼](https://bailian.console.aliyun.com/) | 聚合平台 | ✅ |
| [火山方舟](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | 聚合平台 | ✅ |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | 聚合平台 | ✅ |
| [GiteeAI](https://ai.gitee.com/) | 聚合平台 | ✅ |
| [胜算云](https://www.shengsuanyun.com/?from=CH_KYIPP758) | GPU 平台 | ✅ |
| [优云智算](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | GPU 平台 | ✅ |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | GPU 平台 | ✅ |
| [接口 AI](https://jiekou.ai/) | 聚合平台 | ✅ |
| [302.AI](https://share.302ai.cn/SuTG99) | 聚合平台 | ✅ |
| [小马算力](https://www.tokenpony.cn/453z1) | 聚合平台 | ✅ |
| [百宝箱Tbox](https://www.tbox.cn/open) | 智能体平台 | ✅ |
| [七牛云Qiniu](https://www.qiniu.com/ai/agent) | 聚合平台 | ✅ |

[→ 查看完整集成列表](https://langbot.app/docs/zh/insight/features)

### TTS（语音合成）

| 平台/模型 | 备注 |
|-----------|------|
| [FishAudio](https://fish.audio/zh-CN/discovery/) | [插件](https://github.com/the-lazy-me/NewChatVoice) |
| [海豚 AI](https://www.ttson.cn/?source=thelazy) | [插件](https://github.com/the-lazy-me/NewChatVoice) |
| [AzureTTS](https://portal.azure.com/) | [插件](https://github.com/Ingnaryk/LangBot_AzureTTS) |

### 文生图

| 平台/模型 | 备注 |
|-----------|------|
| 阿里云百炼 | [插件](https://github.com/Thetail001/LangBot_BailianTextToImagePlugin) |

---

## 为什么选择 LangBot？

| 使用场景 | LangBot 如何帮助 |
| --- | --- |
| **社群机器人** | 在 QQ / Discord / Telegram 群里答疑、欢迎新人、按规则互动，并记住群成员的上下文 |
| **私域与客服** | 在微信、企业微信客服里自动接待咨询，基于你的知识库回答，需要时转人工 |
| **把已有 AI 应用接进 IM** | Dify / n8n / Coze 应用一步接入任意聊天平台，无需编写对接代码 |
| **团队内部助手** | 在飞书、钉钉、企业微信里提供知识问答与流程自动化，团队共同管理 |

---

## 为 AI Agent 而生 🤖

LangBot **从设计上就对 Agent 友好** —— 你的编码 Agent（Claude Code、Codex、Copilot、Cursor 等）可以一等公民般地操作、扩展和部署 LangBot：

- **MCP Server** —— LangBot 内置 [Model Context Protocol](https://modelcontextprotocol.io/) 端点 `/mcp`，与 HTTP API 对齐，Agent 可编程式管理机器人、流水线、插件和模型。使用同一套 API Key 鉴权（可在 `config.yaml` 配置全局 Key，或使用用户 Key），无需登录流程。在 Web 面板的 **API 与 MCP** 标签页中配置。
- **CLI（`lbctl`）** —— 独立的 [LangBot CLI](https://github.com/langbot-app/langbot-cli) 让 Agent 在终端通过 Service API 管理已运行实例中的 Workspace。它使用 API Key，支持管理机器人、流水线、知识库、模型、插件、Skill 和 MCP Server。安装方法和命令以 CLI 仓库为准。
- **仓库内 Skills** —— [`skills/`](skills/) 目录是使用 LangBot 的**唯一事实来源**：插件开发、核心开发、端到端测试、部署，以及操作 LangBot / LangBot Space MCP Server。把 Agent 指向这个目录，它就知道如何动手。
- **AGENTS.md** —— 每个仓库都提供 [`AGENTS.md`](AGENTS.md)（软链到 `CLAUDE.md`），描述架构、规范，以及「API 变更必须同步更新 MCP Server 和 skills」的约定。
- **`llms.txt`** —— 面向 LLM 的机器可读项目上下文已发布在官网。

> **云端 / 市场：** [LangBot Space](https://space.langbot.app) 同样开放 MCP Server，Agent 可搜索和查看插件 / MCP / Skill 市场，使用 Personal Access Token 鉴权。

---

## 社区

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-1030838208-blue)](https://qm.qq.com/q/DxZZcNxM1W)

- [Discord 社区](https://discord.gg/wdNEHETs87)
- [QQ 社区群](https://qm.qq.com/q/DxZZcNxM1W)

---

## 贡献者

感谢所有[贡献者](https://github.com/langbot-app/LangBot/graphs/contributors)对 LangBot 的帮助：

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

<!--
## For Code Agents

If you're a code agent based on LLM, you should read [AGENTS.md](AGENTS.md) to understand the project structure and development process before you start any development.
-->

[文档源码](https://github.com/langbot-app/LangBot/tree/master/docs) · [langbot-docs archive](https://github.com/langbot-app/langbot-docs)

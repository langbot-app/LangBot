<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://www.producthunt.com/products/langbot?utm_source=badge-follow&utm_medium=badge&utm_source=badge-langbot" target="_blank"><img src="https://api.producthunt.com/widgets/embed-image/v1/follow.svg?product_id=1077185&theme=light" alt="LangBot - Production&#0045;grade&#0032;IM&#0032;bot&#0032;made&#0032;easy&#0046; | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" /></a>

<h3>Production-grade platform for building agentic IM bots.</h3>
<h4>Quickly build, debug, and ship AI bots to Slack, Discord, Telegram, WeChat, and more.</h4>

English / [简体中文](README_CN.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)

<a href="https://langbot.app">Website</a> ｜
<a href="https://docs.langbot.app/en/insight/features">Features</a> ｜
<a href="https://docs.langbot.app/en/insight/guide">Docs</a> ｜
<a href="https://docs.langbot.app/en/tags/readme">API</a> ｜
<a href="https://space.langbot.app/cloud">Cloud</a> ｜
<a href="https://space.langbot.app">Plugin Market</a> ｜
<a href="https://langbot.featurebase.app/roadmap">Roadmap</a>

</div>

</p>

---

## What is LangBot?

LangBot is an **open-source, production-grade platform** for building AI-powered instant messaging bots. It connects Large Language Models (LLMs) to any chat platform, enabling you to create intelligent agents that can converse, execute tasks, and integrate with your existing workflows.

## 本分支相对官方版本增加 / 增强的能力

相比官方版本，`feat/wecom` 分支围绕**企微智能机器人、企业微信客服、企微应用接管微信客服、Dify 对话连续性、以及私有化部署稳定性**做了持续增强，主要包括以下能力：

1. **企微智能机器人增强**  
   支持更细粒度的 **Pull / Webhook 流式配置**、**pending placeholder 开关与延迟控制**、以及 **Dify 流式输出节流配置**，同时补强拉流生命周期管理、websocket 兼容性与调试日志能力，适合对流式回复体验、稳定性和排障能力要求更高的企微机器人场景。

2. **企业微信客服运行时增强**  
   在官方基础上补充了基于 **Redis Streams** 的调度机制，并增加 **游标检查点持久化、消息状态存储、失败重试、分片处理、token cache** 等能力，显著提升企业微信客服在高消息量、长时间运行、重启恢复等场景下的稳定性与可维护性。

3. **新增“企微应用接管微信客服”类型**  
   新增 `wecom_kf_app` 适配器与对应配置，支持通过**企微应用授权方式**接管和管理微信客服能力，适配更多企业内部权限体系和组织接入模式。

4. **Dify 集成增强**  
   修复 Dify 在 **workflow 流式结束、workflow 输出兼容、流式节流控制** 等方面的若干问题，并新增 **`conversation_id` Redis 持久化机制**，在显式 reset 场景下同步清理绑定，降低 LangBot 重启或会话重建后 Dify 上下文丢失的概率。

5. **企微 / 微信客服链路隔离与上下文保护增强**  
   对 bot stream、pipeline session、客服消息处理链路做了进一步隔离和收口，减少多 bot、多流水线、长链路客服场景下的会话串扰与上下文错配问题。

6. **插件 / RAG / Pipeline 兼容增强**  
   增强旧版 runtime sdk 兼容性，保留 RAG 检索链路中的 session context，并收敛部分 pipeline 异常处理策略，使复杂插件、知识库、老版本运行时共存时更稳定。

7. **检索能力增强**  
   为 **Chroma** 增加全文检索与混合检索支持，提升向量检索之外的能力扩展空间，适合对知识检索效果有更高要求的场景。

8. **部署与运维增强**  
   优化 Docker 镜像体积、构建缓存、Python 路径配置与 compose 镜像来源，并补充围绕 wecomcs 的 Redis 启动与运行文档，更适合长期私有化部署和运维。

如果你的主要使用场景是：**企微智能机器人、企业微信客服、企微应用接管微信客服、Dify 对话连续性、私有化部署稳定性**，那么这个分支相比官方版本会更贴近真实生产需求。

---

### Key Capabilities

- **AI Conversations & Agents** — Multi-turn dialogues, tool calling, multi-modal support, streaming output. Built-in RAG (knowledge base) with deep integration to [Dify](https://dify.ai), [Coze](https://coze.com), [n8n](https://n8n.io), [Langflow](https://langflow.org).
- **Universal IM Platform Support** — One codebase for Discord, Telegram, Slack, LINE, QQ, WeChat, WeCom, Lark, DingTalk, KOOK.
- **Production-Ready** — Access control, rate limiting, sensitive word filtering, comprehensive monitoring, and exception handling. Trusted by enterprises.
- **Plugin Ecosystem** — Hundreds of plugins, event-driven architecture, component extensions, and [MCP protocol](https://modelcontextprotocol.io/) support.
- **Web Management Panel** — Configure, manage, and monitor your bots through an intuitive browser interface. No YAML editing required.
- **Multi-Pipeline Architecture** — Different bots for different scenarios, with comprehensive monitoring and exception handling.

[→ Learn more about all features](https://docs.langbot.app/en/insight/features)

---

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
docker compose up -d
```

### One-Click Cloud Deploy

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**More options:** [Docker](https://docs.langbot.app/en/deploy/langbot/docker) · [Manual](https://docs.langbot.app/en/deploy/langbot/manual) · [BTPanel](https://docs.langbot.app/en/deploy/langbot/one-click/bt) · [Kubernetes](./docker/README_K8S.md)

---

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| QQ | ✅ | Personal & Official API |
| WeCom | ✅ | Enterprise WeChat, External CS, AI Bot |
| WeChat | ✅ | Personal & Official Account |
| Lark | ✅ |  |
| DingTalk | ✅ |  |
| KOOK | ✅ |  |
| Satori | ✅ |  |

---

## Supported LLMs & Integrations

| Provider | Type | Status |
|----------|------|--------|
| [OpenAI](https://platform.openai.com/) | LLM | ✅ |
| [Anthropic](https://www.anthropic.com/) | LLM | ✅ |
| [DeepSeek](https://www.deepseek.com/) | LLM | ✅ |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | LLM | ✅ |
| [xAI](https://x.ai/) | LLM | ✅ |
| [Moonshot](https://www.moonshot.cn/) | LLM | ✅ |
| [Zhipu AI](https://open.bigmodel.cn/) | LLM | ✅ |
| [Ollama](https://ollama.com/) | Local LLM | ✅ |
| [LM Studio](https://lmstudio.ai/) | Local LLM | ✅ |
| [Dify](https://dify.ai) | LLMOps | ✅ |
| [MCP](https://modelcontextprotocol.io/) | Protocol | ✅ |
| [SiliconFlow](https://siliconflow.cn/) | Gateway | ✅ |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | Gateway | ✅ |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | Gateway | ✅ |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | Gateway | ✅ |
| [GiteeAI](https://ai.gitee.com/) | Gateway | ✅ |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | GPU Platform | ✅ |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | GPU Platform | ✅ |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | GPU Platform | ✅ |
| [接口 AI](https://jiekou.ai/) | Gateway | ✅ |
| [302.AI](https://share.302.ai/SuTG99) | Gateway | ✅ |

[→ View all integrations](https://docs.langbot.app/en/insight/features)

---

## Why LangBot?

| Use Case | How LangBot Helps |
|----------|-------------------|
| **Customer Support** | Deploy AI agents to Slack/Discord/Telegram that answer questions using your knowledge base |
| **Internal Tools** | Connect n8n/Dify workflows to WeCom/DingTalk for automated business processes |
| **Community Management** | Moderate QQ/Discord groups with AI-powered content filtering and interaction |
| **Multi-Platform Presence** | One bot, all platforms. Manage from a single dashboard |

---

## Live Demo

**Try it now:** https://demo.langbot.dev/
- Email: `demo@langbot.app`
- Password: `langbot123456`

*Note: Public demo environment. Do not enter sensitive information.*

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

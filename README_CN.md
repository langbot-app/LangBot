<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://hellogithub.com/repository/langbot-app/LangBot" target="_blank"><img src="https://abroad.hellogithub.com/v1/widgets/recommend.svg?rid=5ce8ae2aa4f74316bf393b57b952433c&claim_uid=gtmc6YWjMZkT21R" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>

<h3>生产级 AI 即时通信机器人开发平台。</h3>
<h4>快速构建、调试和部署 AI 机器人到微信、QQ、飞书、Slack、Discord、Telegram 等平台。</h4>

[English](README.md) / 简体中文 / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-1030838208-blue)](https://qm.qq.com/q/DxZZcNxM1W)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)
[![star](https://gitcode.com/RockChinQ/LangBot/star/badge.svg)](https://gitcode.com/RockChinQ/LangBot)

<a href="https://langbot.app">官网</a> ｜
<a href="https://docs.langbot.app/zh/insight/features.html">特性</a> ｜
<a href="https://docs.langbot.app/zh/insight/guide.html">文档</a> ｜
<a href="https://docs.langbot.app/zh/tags/readme.html">API</a> ｜
<a href="https://space.langbot.app">插件市场</a> ｜
<a href="https://langbot.featurebase.app/roadmap">路线图</a>

</div>

</p>

---

## 什么是 LangBot？

LangBot 是一个**开源的生产级平台**，用于构建 AI 驱动的即时通信机器人。它将大语言模型（LLM）连接到各种聊天平台，帮助你创建能够对话、执行任务、并集成到现有工作流程中的智能 Agent。

### 核心能力

- **AI 对话与 Agent** — 多轮对话、工具调用、多模态、流式输出。自带 RAG（知识库），深度集成 [Dify](https://dify.ai)、[Coze](https://coze.com)、[n8n](https://n8n.io)、[Langflow](https://langflow.org) 等 LLMOps 平台。
- **全平台支持** — 一套代码，覆盖 QQ、微信、企业微信、飞书、钉钉、Discord、Telegram、Slack、LINE、KOOK 等平台。
- **生产就绪** — 访问控制、限速、敏感词过滤、全面监控与异常处理，已被多家企业采用。
- **插件生态** — 数百个插件，事件驱动架构，组件扩展，适配 [MCP 协议](https://modelcontextprotocol.io/)。
- **Web 管理面板** — 通过浏览器直观地配置、管理和监控机器人，无需手动编辑配置文件。
- **多流水线架构** — 不同机器人用于不同场景，具备全面的监控和异常处理能力。

[→ 了解更多功能特性](https://docs.langbot.app/zh/insight/features.html)

---

## 快速开始

### 一键启动

```bash
uvx langbot
```

> 需要安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。访问 http://localhost:5300 即可使用。

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

### 一键云部署

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**更多方式：** [Docker](https://docs.langbot.app/zh/deploy/langbot/docker.html) · [手动部署](https://docs.langbot.app/zh/deploy/langbot/manual.html) · [宝塔面板](https://docs.langbot.app/zh/deploy/langbot/one-click/bt.html) · [Kubernetes](./docker/README_K8S.md)

---

## 支持的平台

| 平台 | 状态 | 备注 |
|------|------|------|
| QQ | ✅ | 个人号、官方机器人（频道、私聊、群聊） |
| 微信 | ✅ | 个人微信、微信公众号 |
| 企业微信 | ✅ | 应用消息、对外客服、智能机器人 |
| 飞书 | ✅ |  |
| 钉钉 | ✅ |  |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| KOOK | ✅ |  |

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
| [302.AI](https://share.302.ai/SuTG99) | 聚合平台 | ✅ |
| [小马算力](https://www.tokenpony.cn/453z1) | 聚合平台 | ✅ |
| [百宝箱Tbox](https://www.tbox.cn/open) | 智能体平台 | ✅ |

[→ 查看完整集成列表](https://docs.langbot.app/zh/insight/features.html)

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
|----------|------------------|
| **客户服务** | 将 AI Agent 部署到微信/企微/钉钉/飞书，基于知识库自动回答用户问题 |
| **内部工具** | 将 n8n/Dify 工作流接入企微/钉钉，实现业务流程自动化 |
| **社群运营** | 在 QQ/Discord 群中使用 AI 驱动的内容审核与智能互动 |
| **多平台触达** | 一个机器人，覆盖所有平台。通过统一面板集中管理 |

---

## 在线演示

**立即体验：** https://demo.langbot.dev/
- 邮箱：`demo@langbot.app`
- 密码：`langbot123456`

*注意：公开演示环境，请不要在其中填入任何敏感信息。*

---

## 社区

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-1030838208-blue)](https://qm.qq.com/q/DxZZcNxM1W)

- [Discord 社区](https://discord.gg/wdNEHETs87)
- [QQ 社区群](https://qm.qq.com/q/DxZZcNxM1W)

---

## Star 趋势

[![Star History Chart](https://api.star-history.com/svg?repos=langbot-app/LangBot&type=Date)](https://star-history.com/#langbot-app/LangBot&Date)

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

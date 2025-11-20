<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_en.png" alt="LangBot"/>
</a>

<div align="center">

English / [简体中文](README.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / (PR for your language)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

<a href="https://langbot.app">Home</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">Deployment</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">Plugin</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">Submit Plugin</a>

</div>

</p>

LangBot is an open-source LLM native instant messaging robot development platform, aiming to provide out-of-the-box IM robot development experience, with Agent, RAG, MCP and other LLM application functions, adapting to global instant messaging platforms, and providing rich API interfaces, supporting custom development.

## 📦 Getting Started

#### Quick Start

Use `uvx` to start with one command (need to install [uv](https://docs.astral.sh/uv/getting-started/installation/)):

```bash
uvx langbot
```

Visit http://localhost:5300 to start using it.

#### Docker Compose Deployment

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

Visit http://localhost:5300 to start using it.

Detailed documentation [Docker Deployment](https://docs.langbot.app/en/deploy/langbot/docker.html).

#### One-click Deployment on BTPanel

LangBot has been listed on the BTPanel, if you have installed the BTPanel, you can use the [document](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html) to use it.

#### Zeabur Cloud Deployment

Community contributed Zeabur template.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Railway Cloud Deployment

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### Other Deployment Methods

Directly use the released version to run, see the [Manual Deployment](https://docs.langbot.app/en/deploy/langbot/manual.html) documentation.

#### Kubernetes Deployment

Refer to the [Kubernetes Deployment](./docker/README_K8S.md) documentation.

## 😎 Stay Ahead

Click the Star and Watch button in the upper right corner of the repository to get the latest updates.

![star gif](https://docs.langbot.app/star.gif)

## ✨ Features

- 💬 Chat with LLM / Agent: Supports multiple LLMs, adapt to group chats and private chats; Supports multi-round conversations, tool calls, multi-modal, and streaming output capabilities. Built-in RAG (knowledge base) implementation, and deeply integrates with [Dify](https://dify.ai).
- 🤖 Multi-platform Support: Currently supports QQ, QQ Channel, WeCom, personal WeChat, Lark, DingTalk, Discord, Telegram, etc.
- 🛠️ High Stability, Feature-rich: Native access control, rate limiting, sensitive word filtering, etc. mechanisms; Easy to use, supports multiple deployment methods. Supports multiple pipeline configurations, different bots can be used for different scenarios.
- 🧩 Plugin Extension, Active Community: Support event-driven, component extension, etc. plugin mechanisms; Integrate Anthropic [MCP protocol](https://modelcontextprotocol.io/); Currently has hundreds of plugins.
- 😻 Web UI: Support management LangBot instance through the browser. No need to manually write configuration files.

For more detailed specifications, please refer to the [documentation](https://docs.langbot.app/en/insight/features.html).

Or visit the demo environment: https://demo.langbot.dev/
  - Login information: Email: `demo@langbot.app` Password: `langbot123456`
  - Note: For WebUI demo only, please do not fill in any sensitive information in the public environment.

### Message Platform

| Platform | Status | Remarks |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| Personal QQ | ✅ |  |
| QQ Official API | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| WeCom AI Bot | ✅ |  |
| Personal WeChat | ✅ |  |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### LLMs

| LLM | Status | Remarks |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | Available for any OpenAI interface format model |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | LLM and GPU resource platform |
| [Dify](https://dify.ai) | ✅ | LLMOps platform |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | LLM and GPU resource platform |
| [接口 AI](https://jiekou.ai/) | ✅ | LLM aggregation platform, dedicated to global LLMs |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | LLM and GPU resource platform |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | LLM gateway(MaaS) |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Ollama](https://ollama.com/) | ✅ | Local LLM running platform |
| [LMStudio](https://lmstudio.ai/) | ✅ | Local LLM running platform |
| [GiteeAI](https://ai.gitee.com/) | ✅ | LLM interface gateway(MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | LLM gateway(MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | LLM gateway(MaaS), LLMOps platform |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | LLM gateway(MaaS), LLMOps platform |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | LLM gateway(MaaS) |
| [MCP](https://modelcontextprotocol.io/) | ✅ | Support tool access through MCP protocol |

## 🤝 Community Contribution

Thank you for the following [code contributors](https://github.com/langbot-app/LangBot/graphs/contributors) and other members in the community for their contributions to LangBot:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

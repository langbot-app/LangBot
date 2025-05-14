<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://trendshift.io/repositories/12901" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12901" alt="RockChinQ%2FLangBot | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://langbot.app">Home</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">Deployment</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">Plugin</a> ｜
<a href="https://github.com/RockChinQ/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">Submit Plugin</a>

<div align="center">
😎High Stability, 🧩Extension Supported, 🦄Multi-modal - LLM Native Instant Messaging Bot Platform🤖  
</div>

<br/>


[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/RockChinQ/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/RockChinQ/LangBot)](https://github.com/RockChinQ/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

[简体中文](README.md) / [English](README_EN.md) / [日本語](README_JP.md) / (PR for your language)

</div>

</p>

## ✨ Features

- 💬 Chat with LLM / Agent: Supports multiple LLMs, adapt to group chats and private chats; Supports multi-round conversations, tool calls, and multi-modal capabilities. Deeply integrates with [Dify](https://dify.ai). Currently supports QQ, QQ Channel, WeCom, personal WeChat, Lark, DingTalk, Discord, Telegram, etc.
- 🛠️ High Stability, Feature-rich: Native access control, rate limiting, sensitive word filtering, etc. mechanisms; Easy to use, supports multiple deployment methods. Supports multiple pipeline configurations, different bots can be used for different scenarios.
- 🧩 Plugin Extension, Active Community: Support event-driven, component extension, etc. plugin mechanisms; Integrate Anthropic [MCP protocol](https://modelcontextprotocol.io/); Currently has hundreds of plugins.
- 😻 [New] Web UI: Support management LangBot instance through the browser. No need to manually write configuration files.

## 📦 Getting Started

#### Docker Compose Deployment

```bash
git clone https://github.com/RockChinQ/LangBot
cd LangBot
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

## 📸 Demo

<img alt="bots" src="https://docs.langbot.app/webui/bot-page.png" width="400px"/>

<img alt="bots" src="https://docs.langbot.app/webui/create-model.png" width="400px"/>

<img alt="bots" src="https://docs.langbot.app/webui/edit-pipeline.png" width="400px"/>

<img alt="bots" src="https://docs.langbot.app/webui/plugin-market.png" width="400px"/>

<img alt="Reply Effect (with Internet Plugin)" src="https://docs.langbot.app/QChatGPT-0516.png" width="500px"/>

- WebUI Demo: https://demo.langbot.dev/
    - Login information: Email: `demo@langbot.app` Password: `langbot123456`
    - Note: Only the WebUI effect is shown, please do not fill in any sensitive information in the public environment.

## 🔌 Component Compatibility

### Message Platform

| Platform | Status | Remarks |
| --- | --- | --- |
| Personal QQ | ✅ |  |
| QQ Official API | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| Personal WeChat | ✅ | Use [Gewechat](https://github.com/Devo919/Gewechat) to access |
| Lark | ✅ |  |
| DingTalk | ✅ |  |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | 🚧 |  |
| WhatsApp | 🚧 |  |

🚧: In development

### LLMs

| LLM | Status | Remarks |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | Available for any OpenAI interface format model |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [Dify](https://dify.ai) | ✅ | LLMOps platform |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | LLM and GPU resource platform |
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

Thank you for the following [code contributors](https://github.com/RockChinQ/LangBot/graphs/contributors) and other members in the community for their contributions to LangBot:

<a href="https://github.com/RockChinQ/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=RockChinQ/LangBot" />
</a>

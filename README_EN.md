<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://trendshift.io/repositories/12901" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12901" alt="RockChinQ%2FLangBot | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://docs.langbot.app">Home</a> ｜
<a href="https://docs.langbot.app/insight/intro.htmll">Features</a> ｜
<a href="https://docs.langbot.app/insight/guide.html">Deployment</a> ｜
<a href="https://docs.langbot.app/usage/faq.html">FAQ</a> ｜
<a href="https://docs.langbot.app/plugin/plugin-intro.html">Plugin</a> ｜
<a href="https://github.com/RockChinQ/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">Submit Plugin</a>

<div align="center">
😎High Stability, 🧩Extension Supported, 🦄Multi-modal - LLM Native Instant Messaging Bot Platform🤖  
</div>

<br/>


[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/RockChinQ/LangBot)](https://github.com/RockChinQ/LangBot/releases/latest)
 ![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.qchatgpt.rockchin.top%2Fapi%2Fv2%2Fview%2Frealtime%2Fcount_query%3Fminute%3D10080&query=%24.data.count&label=Usage(7days))
<img src="https://img.shields.io/badge/python-3.10 | 3.11 | 3.12-blue.svg" alt="python">

[简体中文](README.md) / [English](README_EN.md) / [日本語](README_JP.md)

</div>

</p>

## ✨ Features

- 💬 Chat with LLM / Agent: Supports multiple LLMs, adapt to group chats and private chats; Supports multi-round conversations, tool calls, and multi-modal capabilities. Deeply integrates with [Dify](https://dify.ai). Currently supports QQ, QQ Channel, WeCom, Lark, Discord, personal WeChat, and will support WhatsApp, Telegram, etc. in the future.
- 🛠️ High Stability, Feature-rich: Native access control, rate limiting, sensitive word filtering, etc. mechanisms; Easy to use, supports multiple deployment methods.
- 🧩 Plugin Extension, Active Community: Support event-driven, component extension, etc. plugin mechanisms; Rich ecology, currently has dozens of [plugins](https://docs.langbot.app/plugin/plugin-intro.html)
- 😻 [New] Web UI: Support management LangBot instance through the browser, for details, see [documentation](https://docs.langbot.app/webui/intro.html)

## 📦 Getting Started

> [!IMPORTANT]
>
> - Before you start deploying in any way, please read the [New User Guide](https://docs.langbot.app/insight/guide.html).  
> - All documentation is in Chinese, we will provide i18n version in the near future.

#### Docker Compose Deployment

Suitable for users familiar with Docker, see the [Docker Deployment](https://docs.langbot.app/deploy/langbot/docker.html) documentation.

#### One-click Deployment on BTPanel

LangBot has been listed on the BTPanel, if you have installed the BTPanel, you can use the [document](https://docs.langbot.app/deploy/langbot/one-click/bt.html) to use it.

#### Zeabur Cloud Deployment

Community contributed Zeabur template.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)

#### Railway Cloud Deployment

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### Other Deployment Methods

Directly use the released version to run, see the [Manual Deployment](https://docs.langbot.app/deploy/langbot/manual.html) documentation.

## 📸 Demo

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
| WeChat Official Account | ✅ |  |
| Lark | ✅ |  |
| Discord | ✅ |  |
| Personal WeChat | ✅ | Use [Gewechat](https://github.com/Devo919/Gewechat) to access |
| Telegram | 🚧 |  |
| WhatsApp | 🚧 |  |
| DingTalk | 🚧 |  |

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
| [Ollama](https://ollama.com/) | ✅ | Local LLM running platform |
| [LMStudio](https://lmstudio.ai/) | ✅ | Local LLM running platform |
| [GiteeAI](https://ai.gitee.com/) | ✅ | LLM interface gateway(MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | LLM gateway(MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | LLM gateway(MaaS), LLMOps platform |

## 🤝 Community Contribution

Thanks to the following contributors and everyone in the community for their contributions.


<a href="https://github.com/RockChinQ/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=RockChinQ/LangBot" />
</a>




<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://trendshift.io/repositories/12901" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12901" alt="RockChinQ%2FLangBot | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://docs.langbot.app">项目主页</a> ｜
<a href="https://docs.langbot.app/insight/intro.htmll">功能介绍</a> ｜
<a href="https://docs.langbot.app/insight/guide.html">部署文档</a> ｜
<a href="https://docs.langbot.app/usage/faq.html">常见问题</a> ｜
<a href="https://docs.langbot.app/plugin/plugin-intro.html">插件介绍</a> ｜
<a href="https://github.com/RockChinQ/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">提交插件</a>

<div align="center">
😎高稳定、🧩支持扩展、🦄多模态 - 大模型原生即时通信机器人平台🤖  
</div>

<br/>


[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-1030838208-blue)](https://qm.qq.com/q/PF9OuQCCcM)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/RockChinQ/LangBot)](https://github.com/RockChinQ/LangBot/releases/latest)
 ![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.qchatgpt.rockchin.top%2Fapi%2Fv2%2Fview%2Frealtime%2Fcount_query%3Fminute%3D10080&query=%24.data.count&label=%E4%BD%BF%E7%94%A8%E9%87%8F%EF%BC%887%E6%97%A5%EF%BC%89)
<img src="https://img.shields.io/badge/python-3.10 | 3.11 | 3.12-blue.svg" alt="python">

[简体中文](README.md) / [English](README_EN.md) / [日本語](README_JP.md)

</div>

</p>

## ✨ 特性

- 💬 大模型对话、Agent：支持多种大模型，适配群聊和私聊；具有多轮对话、工具调用、多模态能力，并深度适配 [Dify](https://dify.ai)。目前支持 QQ、QQ频道、企业微信、飞书、Discord、个人微信，后续还将支持 WhatsApp、Telegram 等平台。
- 🛠️ 高稳定性、功能完备：原生支持访问控制、限速、敏感词过滤等机制；配置简单，支持多种部署方式。
- 🧩 插件扩展、活跃社区：支持事件驱动、组件扩展等插件机制；丰富生态，目前已有数十个[插件](https://docs.langbot.app/plugin/plugin-intro.html)
- 😻 [New] Web 管理面板：支持通过浏览器管理 LangBot 实例，具体支持功能，查看[文档](https://docs.langbot.app/webui/intro.html)

## 📦 开始使用

> [!IMPORTANT]
>
> 在您开始任何方式部署之前，请务必阅读[新手指引](https://docs.langbot.app/insight/guide.html)。

#### Docker Compose 部署

适合熟悉 Docker 的用户，查看文档[Docker 部署](https://docs.langbot.app/deploy/langbot/docker.html)。

#### 宝塔面板部署

已上架宝塔面板，若您已安装宝塔面板，可以根据[文档](https://docs.langbot.app/deploy/langbot/one-click/bt.html)使用。

#### Zeabur 云部署

社区贡献的 Zeabur 模板。

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)

#### Railway 云部署

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### 手动部署

直接使用发行版运行，查看文档[手动部署](https://docs.langbot.app/deploy/langbot/manual.html)。

## 📸 效果展示

<img alt="回复效果（带有联网插件）" src="https://docs.langbot.app/QChatGPT-0516.png" width="500px"/>

- WebUI Demo: https://demo.langbot.dev/
    - 登录信息：邮箱：`demo@langbot.app` 密码：`langbot123456`
    - 注意：仅展示webui效果，公开环境，请不要在其中填入您的任何敏感信息。

## 🔌 组件兼容性

### 消息平台

| 平台 | 状态 | 备注 |
| --- | --- | --- |
| QQ 个人号 | ✅ | QQ 个人号私聊、群聊 |
| QQ 官方机器人 | ✅ | QQ 官方机器人，支持频道、私聊、群聊 |
| 企业微信 | ✅ |  |
| 微信公众号 | ✅ |  |
| 飞书 | ✅ |  |
| Discord | ✅ |  |
| 个人微信 | ✅ | 使用 [Gewechat](https://github.com/Devo919/Gewechat) 接入 |
| Telegram | 🚧 |  |
| WhatsApp | 🚧 |  |
| 钉钉 | 🚧 |  |

🚧: 正在开发中

### 大模型

| 模型 | 状态 | 备注 |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | 可接入任何 OpenAI 接口格式模型 |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [智谱AI](https://open.bigmodel.cn/) | ✅ |  |
| [Dify](https://dify.ai) | ✅ | LLMOps 平台 |
| [Ollama](https://ollama.com/) | ✅ | 本地大模型运行平台 |
| [LMStudio](https://lmstudio.ai/) | ✅ | 本地大模型运行平台 |
| [GiteeAI](https://ai.gitee.com/) | ✅ | 大模型接口聚合平台 |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | 大模型聚合平台 |
| [阿里云百炼](https://bailian.console.aliyun.com/) | ✅ | 大模型聚合平台, LLMOps 平台 |

## 😘 社区贡献

LangBot 离不开以下贡献者和社区内所有人的贡献，我们欢迎任何形式的贡献和反馈。


<a href="https://github.com/RockChinQ/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=RockChinQ/LangBot" />
</a>

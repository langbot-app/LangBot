
<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://trendshift.io/repositories/12901" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12901" alt="RockChinQ%2FLangBot | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://langbot.app">项目主页</a> ｜
<a href="https://docs.langbot.app/zh/insight/guide.html">部署文档</a> ｜
<a href="https://docs.langbot.app/zh/plugin/plugin-intro.html">插件介绍</a> ｜
<a href="https://github.com/RockChinQ/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">提交插件</a>

<div align="center">
😎高稳定、🧩支持扩展、🦄多模态 - 大模型原生即时通信机器人平台🤖  
</div>

<br/>

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-966235608-blue)](https://qm.qq.com/q/JLi38whHum)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/RockChinQ/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/RockChinQ/LangBot)](https://github.com/RockChinQ/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![star](https://gitcode.com/RockChinQ/LangBot/star/badge.svg)](https://gitcode.com/RockChinQ/LangBot)

[简体中文](README.md) / [English](README_EN.md) / [日本語](README_JP.md) / (PR for your language)

</div>

</p>

## ✨ 特性

- 💬 大模型对话、Agent：支持多种大模型，适配群聊和私聊；具有多轮对话、工具调用、多模态能力，并深度适配 [Dify](https://dify.ai)。目前支持 QQ、QQ频道、企业微信、个人微信、飞书、Discord、Telegram 等平台。
- 🛠️ 高稳定性、功能完备：原生支持访问控制、限速、敏感词过滤等机制；配置简单，支持多种部署方式。支持多流水线配置，不同机器人用于不同应用场景。
- 🧩 插件扩展、活跃社区：支持事件驱动、组件扩展等插件机制；适配 Anthropic [MCP 协议](https://modelcontextprotocol.io/)；目前已有数百个插件。
- 😻 Web 管理面板：支持通过浏览器管理 LangBot 实例，不再需要手动编写配置文件。

## 📦 开始使用

#### Docker Compose 部署

```bash
git clone https://github.com/RockChinQ/LangBot
cd LangBot
docker compose up -d
```

访问 http://localhost:5300 即可开始使用。

详细文档[Docker 部署](https://docs.langbot.app/zh/deploy/langbot/docker.html)。

#### 宝塔面板部署

已上架宝塔面板，若您已安装宝塔面板，可以根据[文档](https://docs.langbot.app/zh/deploy/langbot/one-click/bt.html)使用。

#### Zeabur 云部署

社区贡献的 Zeabur 模板。

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)

#### Railway 云部署

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### 手动部署

直接使用发行版运行，查看文档[手动部署](https://docs.langbot.app/zh/deploy/langbot/manual.html)。

## 📸 效果展示

<img alt="bots" src="https://docs.langbot.app/webui/bot-page.png" width="450px"/>

<img alt="bots" src="https://docs.langbot.app/webui/create-model.png" width="450px"/>

<img alt="bots" src="https://docs.langbot.app/webui/edit-pipeline.png" width="450px"/>

<img alt="bots" src="https://docs.langbot.app/webui/plugin-market.png" width="450px"/>

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
| 企微对外客服 | ✅ |  |
| 个人微信 | ✅ | 使用 [Gewechat](https://github.com/Devo919/Gewechat) 接入 |
| 微信公众号 | ✅ |  |
| 飞书 | ✅ |  |
| 钉钉 | ✅ |  |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | 🚧 |  |
| WhatsApp | 🚧 |  |

🚧: 正在开发中

### 大模型能力

| 模型 | 状态 | 备注 |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | 可接入任何 OpenAI 接口格式模型 |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [智谱AI](https://open.bigmodel.cn/) | ✅ |  |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | 大模型和 GPU 资源平台 |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | LLMOps 平台 |
| [Ollama](https://ollama.com/) | ✅ | 本地大模型运行平台 |
| [LMStudio](https://lmstudio.ai/) | ✅ | 本地大模型运行平台 |
| [GiteeAI](https://ai.gitee.com/) | ✅ | 大模型接口聚合平台 |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | 大模型聚合平台 |
| [阿里云百炼](https://bailian.console.aliyun.com/) | ✅ | 大模型聚合平台, LLMOps 平台 |
| [火山方舟](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | 大模型聚合平台, LLMOps 平台 |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | 大模型聚合平台 |
| [MCP](https://modelcontextprotocol.io/) | ✅ | 支持通过 MCP 协议获取工具 |

### TTS

| 平台/模型 | 备注 |
| --- | --- |
| [FishAudio](https://fish.audio/zh-CN/discovery/) | [插件](https://github.com/the-lazy-me/NewChatVoice) |
| [海豚 AI](https://www.ttson.cn/?source=thelazy) | [插件](https://github.com/the-lazy-me/NewChatVoice) |
| [AzureTTS](https://portal.azure.com/) | [插件](https://github.com/Ingnaryk/LangBot_AzureTTS) |

### 文生图

| 平台/模型 | 备注 |
| --- | --- |
| 阿里云百炼 | [插件](https://github.com/Thetail001/LangBot_BailianTextToImagePlugin)

## 😘 社区贡献

感谢以下[代码贡献者](https://github.com/RockChinQ/LangBot/graphs/contributors)和社区里其他成员对 LangBot 的贡献：

<a href="https://github.com/RockChinQ/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=RockChinQ/LangBot" />
</a>

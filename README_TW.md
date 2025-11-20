<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_zh.png" alt="LangBot"/>
</a>

<div align="center"><a href="https://hellogithub.com/repository/langbot-app/LangBot" target="_blank"><img src="https://abroad.hellogithub.com/v1/widgets/recommend.svg?rid=5ce8ae2aa4f74316bf393b57b952433c&claim_uid=gtmc6YWjMZkT21R" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>

[English](README_EN.md) / [简体中文](README.md) / 繁體中文 / [日本語](README_JP.md) / (PR for your language)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-966235608-blue)](https://qm.qq.com/q/JLi38whHum)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![star](https://gitcode.com/RockChinQ/LangBot/star/badge.svg)](https://gitcode.com/RockChinQ/LangBot)

<a href="https://langbot.app">主頁</a> ｜
<a href="https://docs.langbot.app/zh/insight/guide.html">部署文件</a> ｜
<a href="https://docs.langbot.app/zh/plugin/plugin-intro.html">外掛介紹</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">提交外掛</a>

</div>

</p>

LangBot 是一個開源的大語言模型原生即時通訊機器人開發平台，旨在提供開箱即用的 IM 機器人開發體驗，具有 Agent、RAG、MCP 等多種 LLM 應用功能，適配全球主流即時通訊平台，並提供豐富的 API 介面，支援自定義開發。

## 📦 開始使用

#### 快速部署

使用 `uvx` 一鍵啟動（需要先安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/) ）：

```bash
uvx langbot
```

訪問 http://localhost:5300 即可開始使用。

#### Docker Compose 部署

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

訪問 http://localhost:5300 即可開始使用。

詳細文件[Docker 部署](https://docs.langbot.app/zh/deploy/langbot/docker.html)。

#### 寶塔面板部署

已上架寶塔面板，若您已安裝寶塔面板，可以根據[文件](https://docs.langbot.app/zh/deploy/langbot/one-click/bt.html)使用。

#### Zeabur 雲端部署

社群貢獻的 Zeabur 模板。

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)

#### Railway 雲端部署

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### 手動部署

直接使用發行版運行，查看文件[手動部署](https://docs.langbot.app/zh/deploy/langbot/manual.html)。

#### Kubernetes 部署

參考 [Kubernetes 部署](./docker/README_K8S.md) 文件。

## 😎 保持更新

點擊倉庫右上角 Star 和 Watch 按鈕，獲取最新動態。

![star gif](https://docs.langbot.app/star.gif)

## ✨ 特性

- 💬 大模型對話、Agent：支援多種大模型，適配群聊和私聊；具有多輪對話、工具調用、多模態、流式輸出能力，自帶 RAG（知識庫）實現，並深度適配 [Dify](https://dify.ai)。
- 🤖 多平台支援：目前支援 QQ、QQ頻道、企業微信、個人微信、飛書、Discord、Telegram 等平台。
- 🛠️ 高穩定性、功能完備：原生支援訪問控制、限速、敏感詞過濾等機制；配置簡單，支援多種部署方式。支援多流水線配置，不同機器人用於不同應用場景。
- 🧩 外掛擴展、活躍社群：支援事件驅動、組件擴展等外掛機制；適配 Anthropic [MCP 協議](https://modelcontextprotocol.io/)；目前已有數百個外掛。
- 😻 Web 管理面板：支援通過瀏覽器管理 LangBot 實例，不再需要手動編寫配置文件。

詳細規格特性請訪問[文件](https://docs.langbot.app/zh/insight/features.html)。

或訪問 demo 環境：https://demo.langbot.dev/  
  - 登入資訊：郵箱：`demo@langbot.app` 密碼：`langbot123456`
  - 注意：僅展示 WebUI 效果，公開環境，請不要在其中填入您的任何敏感資訊。

### 訊息平台

| 平台 | 狀態 | 備註 |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| QQ 個人號 | ✅ | QQ 個人號私聊、群聊 |
| QQ 官方機器人 | ✅ | QQ 官方機器人，支援頻道、私聊、群聊 |
| 微信 | ✅ |  |
| 企微對外客服 | ✅ |  |
| 企微智能機器人 | ✅ |  |
| 微信公眾號 | ✅ |  |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### 大模型能力

| 模型 | 狀態 | 備註 |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | 可接入任何 OpenAI 介面格式模型 |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [智譜AI](https://open.bigmodel.cn/) | ✅ |  |
| [勝算雲](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | 大模型和 GPU 資源平台 |
| [優雲智算](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | 大模型和 GPU 資源平台 |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | 大模型和 GPU 資源平台 |
| [接口 AI](https://jiekou.ai/) | ✅ | 大模型聚合平台，專注全球大模型接入 |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | 大模型聚合平台 |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | LLMOps 平台 |
| [Ollama](https://ollama.com/) | ✅ | 本地大模型運行平台 |
| [LMStudio](https://lmstudio.ai/) | ✅ | 本地大模型運行平台 |
| [GiteeAI](https://ai.gitee.com/) | ✅ | 大模型介面聚合平台 |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | 大模型聚合平台 |
| [阿里雲百煉](https://bailian.console.aliyun.com/) | ✅ | 大模型聚合平台, LLMOps 平台 |
| [火山方舟](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | 大模型聚合平台, LLMOps 平台 |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | 大模型聚合平台 |
| [MCP](https://modelcontextprotocol.io/) | ✅ | 支援通過 MCP 協議獲取工具 |

### TTS

| 平台/模型 | 備註 |
| --- | --- |
| [FishAudio](https://fish.audio/zh-CN/discovery/) | [外掛](https://github.com/the-lazy-me/NewChatVoice) |
| [海豚 AI](https://www.ttson.cn/?source=thelazy) | [外掛](https://github.com/the-lazy-me/NewChatVoice) |
| [AzureTTS](https://portal.azure.com/) | [外掛](https://github.com/Ingnaryk/LangBot_AzureTTS) |

### 文生圖

| 平台/模型 | 備註 |
| --- | --- |
| 阿里雲百煉 | [外掛](https://github.com/Thetail001/LangBot_BailianTextToImagePlugin)

## 😘 社群貢獻

感謝以下[程式碼貢獻者](https://github.com/langbot-app/LangBot/graphs/contributors)和社群裡其他成員對 LangBot 的貢獻：

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a> 
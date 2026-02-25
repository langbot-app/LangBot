<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://hellogithub.com/repository/langbot-app/LangBot" target="_blank"><img src="https://abroad.hellogithub.com/v1/widgets/recommend.svg?rid=5ce8ae2aa4f74316bf393b57b952433c&claim_uid=gtmc6YWjMZkT21R" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>

<h3>生產級 AI 即時通訊機器人開發平台。</h3>
<h4>快速建構、除錯和部署 AI 機器人到微信、QQ、飛書、Slack、Discord、Telegram 等平台。</h4>

[English](README.md) / [简体中文](README_CN.md) / 繁體中文 / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-966235608-blue)](https://qm.qq.com/q/JLi38whHum)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)
[![star](https://gitcode.com/RockChinQ/LangBot/star/badge.svg)](https://gitcode.com/RockChinQ/LangBot)

<a href="https://langbot.app">官網</a> ｜
<a href="https://docs.langbot.app/zh/insight/features.html">特性</a> ｜
<a href="https://docs.langbot.app/zh/insight/guide.html">文件</a> ｜
<a href="https://docs.langbot.app/zh/tags/readme.html">API</a> ｜
<a href="https://space.langbot.app">外掛市場</a> ｜
<a href="https://langbot.featurebase.app/roadmap">路線圖</a>

</div>

</p>

---

## 什麼是 LangBot？

LangBot 是一個**開源的生產級平台**，用於建構 AI 驅動的即時通訊機器人。它將大語言模型（LLM）連接到各種聊天平台，幫助你創建能夠對話、執行任務、並整合到現有工作流程中的智能 Agent。

### 核心能力

- **AI 對話與 Agent** — 多輪對話、工具調用、多模態、流式輸出。自帶 RAG（知識庫），深度整合 [Dify](https://dify.ai)、[Coze](https://coze.com)、[n8n](https://n8n.io)、[Langflow](https://langflow.org) 等 LLMOps 平台。
- **全平台支援** — 一套程式碼，覆蓋 QQ、微信、企業微信、飛書、釘釘、Discord、Telegram、Slack、LINE、KOOK 等平台。
- **生產就緒** — 存取控制、限速、敏感詞過濾、全面監控與異常處理，已被多家企業採用。
- **外掛生態** — 數百個外掛，事件驅動架構，組件擴展，適配 [MCP 協議](https://modelcontextprotocol.io/)。
- **Web 管理面板** — 透過瀏覽器直觀地配置、管理和監控機器人，無需手動編輯設定檔。
- **多流水線架構** — 不同機器人用於不同場景，具備全面的監控和異常處理能力。

[→ 了解更多功能特性](https://docs.langbot.app/zh/insight/features.html)

---

## 快速開始

### 一鍵啟動

```bash
uvx langbot
```

> 需要安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)。訪問 http://localhost:5300 即可使用。

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

### 一鍵雲端部署

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**更多方式：** [Docker](https://docs.langbot.app/zh/deploy/langbot/docker.html) · [手動部署](https://docs.langbot.app/zh/deploy/langbot/manual.html) · [寶塔面板](https://docs.langbot.app/zh/deploy/langbot/one-click/bt.html) · [Kubernetes](./docker/README_K8S.md)

---

## 支援的平台

| 平台 | 狀態 | 備註 |
|------|------|------|
| QQ | ✅ | 個人號、官方機器人（頻道、私聊、群聊） |
| 微信 | ✅ | 個人微信、微信公眾號 |
| 企業微信 | ✅ | 應用訊息、對外客服、智能機器人 |
| 飛書 | ✅ |  |
| 釘釘 | ✅ |  |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| KOOK | ✅ |  |
| Satori | ✅ |  |

---

## 支援的大模型與整合

| 提供商 | 類型 | 狀態 |
|--------|------|------|
| [OpenAI](https://platform.openai.com/) | LLM | ✅ |
| [Anthropic](https://www.anthropic.com/) | LLM | ✅ |
| [DeepSeek](https://www.deepseek.com/) | LLM | ✅ |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | LLM | ✅ |
| [xAI](https://x.ai/) | LLM | ✅ |
| [Moonshot](https://www.moonshot.cn/) | LLM | ✅ |
| [智譜AI](https://open.bigmodel.cn/) | LLM | ✅ |
| [Ollama](https://ollama.com/) | 本地 LLM | ✅ |
| [LM Studio](https://lmstudio.ai/) | 本地 LLM | ✅ |
| [Dify](https://dify.ai) | LLMOps | ✅ |
| [MCP](https://modelcontextprotocol.io/) | 協議 | ✅ |
| [SiliconFlow](https://siliconflow.cn/) | 聚合平台 | ✅ |
| [阿里雲百煉](https://bailian.console.aliyun.com/) | 聚合平台 | ✅ |
| [火山方舟](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | 聚合平台 | ✅ |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | 聚合平台 | ✅ |
| [GiteeAI](https://ai.gitee.com/) | 聚合平台 | ✅ |
| [勝算雲](https://www.shengsuanyun.com/?from=CH_KYIPP758) | GPU 平台 | ✅ |
| [優雲智算](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | GPU 平台 | ✅ |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | GPU 平台 | ✅ |
| [接口 AI](https://jiekou.ai/) | 聚合平台 | ✅ |
| [302.AI](https://share.302.ai/SuTG99) | 聚合平台 | ✅ |

### TTS（語音合成）

| 平台/模型 | 備註 |
|-----------|------|
| [FishAudio](https://fish.audio/zh-CN/discovery/) | [外掛](https://github.com/the-lazy-me/NewChatVoice) |
| [海豚 AI](https://www.ttson.cn/?source=thelazy) | [外掛](https://github.com/the-lazy-me/NewChatVoice) |
| [AzureTTS](https://portal.azure.com/) | [外掛](https://github.com/Ingnaryk/LangBot_AzureTTS) |

### 文生圖

| 平台/模型 | 備註 |
|-----------|------|
| 阿里雲百煉 | [外掛](https://github.com/Thetail001/LangBot_BailianTextToImagePlugin) |

[→ 查看完整整合列表](https://docs.langbot.app/zh/insight/features.html)

---

## 為什麼選擇 LangBot？

| 使用場景 | LangBot 如何幫助 |
|----------|------------------|
| **客戶服務** | 將 AI Agent 部署到微信/企微/釘釘/飛書，基於知識庫自動回答使用者問題 |
| **內部工具** | 將 n8n/Dify 工作流接入企微/釘釘，實現業務流程自動化 |
| **社群運營** | 在 QQ/Discord 群中使用 AI 驅動的內容審核與智能互動 |
| **多平台觸達** | 一個機器人，覆蓋所有平台。透過統一面板集中管理 |

---

## 線上演示

**立即體驗：** https://demo.langbot.dev/
- 信箱：`demo@langbot.app`
- 密碼：`langbot123456`

*注意：公開演示環境，請不要在其中填入任何敏感資訊。*

---

## 社群

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)
[![QQ Group](https://img.shields.io/badge/%E7%A4%BE%E5%8C%BAQQ%E7%BE%A4-966235608-blue)](https://qm.qq.com/q/JLi38whHum)

- [Discord 社群](https://discord.gg/wdNEHETs87)
- [QQ 社群群](https://qm.qq.com/q/JLi38whHum)

---

## Star 趨勢

[![Star History Chart](https://api.star-history.com/svg?repos=langbot-app/LangBot&type=Date)](https://star-history.com/#langbot-app/LangBot&Date)

---

## 貢獻者

感謝所有[貢獻者](https://github.com/langbot-app/LangBot/graphs/contributors)對 LangBot 的幫助：

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

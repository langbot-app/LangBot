<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://trendshift.io/repositories/12901" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12901" alt="RockChinQ%2FLangBot | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://langbot.app">ホーム</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">デプロイ</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">プラグイン</a> ｜
<a href="https://github.com/RockChinQ/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">プラグインの提出</a>

<div align="center">
😎高い安定性、🧩拡張サポート、🦄マルチモーダル - LLMネイティブインスタントメッセージングボットプラットフォーム🤖  
</div>

<br/>

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/RockChinQ/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/RockChinQ/LangBot)](https://github.com/RockChinQ/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

[简体中文](README.md) / [English](README_EN.md) / [日本語](README_JP.md) / (PR for your language)

</div>

</p>

## ✨ 機能

- 💬 LLM / エージェントとのチャット: 複数のLLMをサポートし、グループチャットとプライベートチャットに対応。マルチラウンドの会話、ツールの呼び出し、マルチモーダル機能をサポート。 [Dify](https://dify.ai) と深く統合。現在、QQ、QQ チャンネル、WeChat、個人 WeChat、Lark、DingTalk、Discord、Telegram など、複数のプラットフォームをサポートしています。
- 🛠️ 高い安定性、豊富な機能: ネイティブのアクセス制御、レート制限、敏感な単語のフィルタリングなどのメカニズムをサポート。使いやすく、複数のデプロイ方法をサポート。複数のパイプライン設定をサポートし、異なるボットを異なる用途に使用できます。
- 🧩 プラグイン拡張、活発なコミュニティ: イベント駆動、コンポーネント拡張などのプラグインメカニズムをサポート。適配 Anthropic [MCP プロトコル](https://modelcontextprotocol.io/)；豊富なエコシステム、現在数百のプラグインが存在。
- 😻 Web UI: ブラウザを通じてLangBotインスタンスを管理することをサポート。

## 📦 始め方

#### Docker Compose デプロイ

```bash
git clone https://github.com/RockChinQ/LangBot
cd LangBot
docker compose up -d
```

http://localhost:5300 にアクセスして使用を開始します。

詳細なドキュメントは[Dockerデプロイ](https://docs.langbot.app/en/deploy/langbot/docker.html)を参照してください。

#### BTPanelでのワンクリックデプロイ

LangBotはBTPanelにリストされています。BTPanelをインストールしている場合は、[ドキュメント](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html)を使用して使用できます。

#### Zeaburクラウドデプロイ

コミュニティが提供するZeaburテンプレート。

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Railwayクラウドデプロイ

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### その他のデプロイ方法

リリースバージョンを直接使用して実行します。[手動デプロイ](https://docs.langbot.app/en/deploy/langbot/manual.html)のドキュメントを参照してください。

## 📸 デモ

<img alt="bots" src="https://docs.langbot.app/webui/bot-page.png" width="400px"/>

<img alt="bots" src="https://docs.langbot.app/webui/create-model.png" width="400px"/>

<img alt="bots" src="https://docs.langbot.app/webui/edit-pipeline.png" width="400px"/>

<img alt="bots" src="https://docs.langbot.app/webui/plugin-market.png" width="400px"/>

<img alt="返信効果（インターネットプラグイン付き）" src="https://docs.langbot.app/QChatGPT-0516.png" width="500px"/>

- WebUIデモ: https://demo.langbot.dev/
    - ログイン情報: メール: `demo@langbot.app` パスワード: `langbot123456`
    - 注意: WebUIの効果のみを示しています。公開環境では、機密情報を入力しないでください。

## 🔌 コンポーネントの互換性

### メッセージプラットフォーム

| プラットフォーム | ステータス | 備考 |
| --- | --- | --- |
| 個人QQ | ✅ |  |
| QQ公式API | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| 個人WeChat | ✅ | [Gewechat](https://github.com/Devo919/Gewechat)を使用して接続 |
| Lark | ✅ |  |
| DingTalk | ✅ |  |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | 🚧 |  |
| WhatsApp | 🚧 |  |

🚧: 開発中

### LLMs

| LLM | ステータス | 備考 |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | 任意のOpenAIインターフェース形式モデルに対応 |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | 大模型とGPUリソースプラットフォーム |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | LLMOpsプラットフォーム |
| [Ollama](https://ollama.com/) | ✅ | ローカルLLM実行プラットフォーム |
| [LMStudio](https://lmstudio.ai/) | ✅ | ローカルLLM実行プラットフォーム |
| [GiteeAI](https://ai.gitee.com/) | ✅ | LLMインターフェースゲートウェイ(MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | LLMゲートウェイ(MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | LLMゲートウェイ(MaaS), LLMOpsプラットフォーム |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | LLMゲートウェイ(MaaS), LLMOpsプラットフォーム |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | LLMゲートウェイ(MaaS) |
| [MCP](https://modelcontextprotocol.io/) | ✅ | MCPプロトコルをサポート |

## 🤝 コミュニティ貢献

LangBot への貢献に対して、以下の [コード貢献者](https://github.com/RockChinQ/LangBot/graphs/contributors) とコミュニティの他のメンバーに感謝します。

<a href="https://github.com/RockChinQ/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=RockChinQ/LangBot" />
</a>

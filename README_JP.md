<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://trendshift.io/repositories/12901" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12901" alt="RockChinQ%2FLangBot | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://docs.langbot.app">ホーム</a> ｜
<a href="https://docs.langbot.app/insight/intro.htmll">機能</a> ｜
<a href="https://docs.langbot.app/insight/guide.html">デプロイ</a> ｜
<a href="https://docs.langbot.app/usage/faq.html">FAQ</a> ｜
<a href="https://docs.langbot.app/plugin/plugin-intro.html">プラグイン</a> ｜
<a href="https://github.com/RockChinQ/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">プラグインの提出</a>

<div align="center">
😎高い安定性、🧩拡張サポート、🦄マルチモーダル - LLMネイティブインスタントメッセージングボットプラットフォーム🤖  
</div>

<br/>

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/RockChinQ/LangBot)](https://github.com/RockChinQ/LangBot/releases/latest)
 ![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.qchatgpt.rockchin.top%2Fapi%2Fv2%2Fview%2Frealtime%2Fcount_query%3Fminute%3D10080&query=%24.data.count&label=Usage(7days))
<img src="https://img.shields.io/badge/python-3.10 | 3.11 | 3.12-blue.svg" alt="python">

[简体中文](README.md) / [English](README_EN.md) / [日本語](README_JP.md)

</div>

</p>

## ✨ 機能

- 💬 LLM / エージェントとのチャット: 複数のLLMをサポートし、グループチャットとプライベートチャットに対応。マルチラウンドの会話、ツールの呼び出し、マルチモーダル機能をサポート。 [Dify](https://dify.ai) と深く統合。現在、QQ、QQ チャンネル、WeChat、個人 WeChat、Lark、DingTalk、Discord、Telegram など、複数のプラットフォームをサポートしています。
- 🛠️ 高い安定性、豊富な機能: ネイティブのアクセス制御、レート制限、敏感な単語のフィルタリングなどのメカニズムをサポート。使いやすく、複数のデプロイ方法をサポート。
- 🧩 プラグイン拡張、活発なコミュニティ: イベント駆動、コンポーネント拡張などのプラグインメカニズムをサポート。豊富なエコシステム、現在数十の[プラグイン](https://docs.langbot.app/plugin/plugin-intro.html)が存在。
- 😻 [新機能] Web UI: ブラウザを通じてLangBotインスタンスを管理することをサポート。詳細は[ドキュメント](https://docs.langbot.app/webui/intro.html)を参照。

## 📦 始め方

> [!IMPORTANT]
>
> - どのデプロイ方法を始める前に、必ず[新規ユーザーガイド](https://docs.langbot.app/insight/guide.html)をお読みください。  
> - すべてのドキュメントは中国語で提供されています。近い将来、i18nバージョンを提供する予定です。

#### Docker Compose デプロイ

Dockerに慣れているユーザーに適しています。[Dockerデプロイ](https://docs.langbot.app/deploy/langbot/docker.html)のドキュメントを参照してください。

#### BTPanelでのワンクリックデプロイ

LangBotはBTPanelにリストされています。BTPanelをインストールしている場合は、[ドキュメント](https://docs.langbot.app/deploy/langbot/one-click/bt.html)を使用して使用できます。

#### Zeaburクラウドデプロイ

コミュニティが提供するZeaburテンプレート。

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/zh-CN/templates/ZKTBDH)

#### Railwayクラウドデプロイ

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### その他のデプロイ方法

リリースバージョンを直接使用して実行します。[手動デプロイ](https://docs.langbot.app/deploy/langbot/manual.html)のドキュメントを参照してください。

## 📸 デモ

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
| 個人WeChat | ✅ | [Gewechat](https://github.com/Devo919/Gewechat)を使用して接続 |
| Lark | ✅ |  |
| DingTalk | ✅ |  |
| Discord | ✅ |  |
| Telegram | ✅ |  |
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
| [Dify](https://dify.ai) | ✅ | LLMOpsプラットフォーム |
| [Ollama](https://ollama.com/) | ✅ | ローカルLLM実行プラットフォーム |
| [LMStudio](https://lmstudio.ai/) | ✅ | ローカルLLM実行プラットフォーム |
| [GiteeAI](https://ai.gitee.com/) | ✅ | LLMインターフェースゲートウェイ(MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | LLMゲートウェイ(MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | LLMゲートウェイ(MaaS), LLMOpsプラットフォーム |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | LLMゲートウェイ(MaaS), LLMOpsプラットフォーム |

## 🤝 コミュニティ貢献

以下の貢献者とコミュニティの皆さんの貢献に感謝します。


<a href="https://github.com/RockChinQ/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=RockChinQ/LangBot" />
</a>



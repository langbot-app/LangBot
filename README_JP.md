<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_en.png" alt="LangBot"/>
</a>

<div align="center">

[English](README_EN.md) / [简体中文](README.md) / [繁體中文](README_TW.md) / 日本語 / (PR for your language)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

<a href="https://langbot.app">ホーム</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">デプロイ</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">プラグイン</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">プラグインの提出</a>

</div>

</p>

LangBot は、エージェント、RAG、MCP などの LLM アプリケーション機能を備えた、オープンソースの LLM ネイティブのインスタントメッセージングロボット開発プラットフォームです。世界中のインスタントメッセージングプラットフォームに適応し、豊富な API インターフェースを提供し、カスタム開発をサポートします。

## 📦 始め方

#### クイックスタート

`uvx` を使用した迅速なデプロイ（[uv](https://docs.astral.sh/uv/getting-started/installation/) が必要です）：

```bash
uvx langbot
```

http://localhost:5300 にアクセスして使用を開始します。

#### Docker Compose デプロイ

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

http://localhost:5300 にアクセスして使用を開始します。

詳細なドキュメントは[Dockerデプロイ](https://docs.langbot.app/en/deploy/langbot/docker.html)を参照してください。

#### Panelでのワンクリックデプロイ

LangBotはBTPanelにリストされています。BTPanelをインストールしている場合は、[ドキュメント](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html)を使用して使用できます。

#### Zeaburクラウドデプロイ

コミュニティが提供するZeaburテンプレート。

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Railwayクラウドデプロイ

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### その他のデプロイ方法

リリースバージョンを直接使用して実行します。[手動デプロイ](https://docs.langbot.app/en/deploy/langbot/manual.html)のドキュメントを参照してください。

#### Kubernetes デプロイ

[Kubernetes デプロイ](./docker/README_K8S.md) ドキュメントを参照してください。

## 😎 最新情報を入手

リポジトリの右上にある Star と Watch ボタンをクリックして、最新の更新を取得してください。

![star gif](https://docs.langbot.app/star.gif)

## ✨ 機能

- 💬 LLM / エージェントとのチャット: 複数のLLMをサポートし、グループチャットとプライベートチャットに対応。マルチラウンドの会話、ツールの呼び出し、マルチモーダル、ストリーミング出力機能をサポート、RAG（知識ベース）を組み込み、[Dify](https://dify.ai) と深く統合。
- 🤖 多プラットフォーム対応: 現在、QQ、QQ チャンネル、WeChat、個人 WeChat、Lark、DingTalk、Discord、Telegram など、複数のプラットフォームをサポートしています。
- 🛠️ 高い安定性、豊富な機能: ネイティブのアクセス制御、レート制限、敏感な単語のフィルタリングなどのメカニズムをサポート。使いやすく、複数のデプロイ方法をサポート。複数のパイプライン設定をサポートし、異なるボットを異なる用途に使用できます。
- 🧩 プラグイン拡張、活発なコミュニティ: イベント駆動、コンポーネント拡張などのプラグインメカニズムをサポート。適配 Anthropic [MCP プロトコル](https://modelcontextprotocol.io/)；豊富なエコシステム、現在数百のプラグインが存在。
- 😻 Web UI: ブラウザを通じてLangBotインスタンスを管理することをサポート。

詳細な仕様については、[ドキュメント](https://docs.langbot.app/en/insight/features.html)を参照してください。

または、デモ環境にアクセスしてください: https://demo.langbot.dev/
  - ログイン情報: メール: `demo@langbot.app` パスワード: `langbot123456`
  - 注意: WebUI のデモンストレーションのみの場合、公開環境では機密情報を入力しないでください。

### メッセージプラットフォーム

| プラットフォーム | ステータス | 備考 |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| 個人QQ | ✅ |  |
| QQ公式API | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| WeCom AI Bot | ✅ |  |
| 個人WeChat | ✅ | |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### LLMs

| LLM | ステータス | 備考 |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | 任意のOpenAIインターフェース形式モデルに対応 |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | 大模型とGPUリソースプラットフォーム |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | 大模型とGPUリソースプラットフォーム |
| [接口 AI](https://jiekou.ai/) | ✅ | LLMゲートウェイ(MaaS) |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | LLMとGPUリソースプラットフォーム |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | LLMゲートウェイ(MaaS) |
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

LangBot への貢献に対して、以下の [コード貢献者](https://github.com/langbot-app/LangBot/graphs/contributors) とコミュニティの他のメンバーに感謝します。

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_en.png" alt="LangBot"/>
</a>

<div align="center">

[English](README_EN.md) / [简体中文](README.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / 한국어 / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

<a href="https://langbot.app">홈</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">배포</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">플러그인</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">플러그인 제출</a>

</div>

</p>

LangBot은 오픈 소스 LLM 네이티브 인스턴트 메시징 로봇 개발 플랫폼으로, Agent, RAG, MCP 등 다양한 LLM 애플리케이션 기능을 갖춘 즉시 사용 가능한 IM 로봇 개발 경험을 제공하며, 글로벌 인스턴트 메시징 플랫폼에 적응하고 풍부한 API 인터페이스를 제공하여 맞춤형 개발을 지원합니다.

## 📦 시작하기

#### 빠른 시작

`uvx`를 사용하여 한 명령으로 시작하세요 ([uv](https://docs.astral.sh/uv/getting-started/installation/) 설치 필요):

```bash
uvx langbot
```

http://localhost:5300을 방문하여 사용을 시작하세요.

#### Docker Compose 배포

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

http://localhost:5300을 방문하여 사용을 시작하세요.

자세한 문서는 [Docker 배포](https://docs.langbot.app/en/deploy/langbot/docker.html)를 참조하세요.

#### BTPanel 원클릭 배포

LangBot은 BTPanel에 등록되어 있습니다. BTPanel을 설치한 경우 [문서](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html)를 사용하여 사용할 수 있습니다.

#### Zeabur 클라우드 배포

커뮤니티에서 제공하는 Zeabur 템플릿입니다.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Railway 클라우드 배포

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### 기타 배포 방법

릴리스 버전을 직접 사용하여 실행하려면 [수동 배포](https://docs.langbot.app/en/deploy/langbot/manual.html) 문서를 참조하세요.

#### Kubernetes 배포

[Kubernetes 배포](./docker/README_K8S.md) 문서를 참조하세요.

## 😎 최신 정보 받기

리포지토리 오른쪽 상단의 Star 및 Watch 버튼을 클릭하여 최신 업데이트를 받으세요.

![star gif](https://docs.langbot.app/star.gif)

## ✨ 기능

- 💬 LLM / Agent와 채팅: 여러 LLM을 지원하며 그룹 채팅 및 개인 채팅에 적응; 멀티 라운드 대화, 도구 호출, 멀티모달, 스트리밍 출력 기능을 지원합니다. 내장된 RAG(지식 베이스) 구현 및 [Dify](https://dify.ai)와 깊이 통합됩니다.
- 🤖 다중 플랫폼 지원: 현재 QQ, QQ Channel, WeCom, 개인 WeChat, Lark, DingTalk, Discord, Telegram 등을 지원합니다.
- 🛠️ 높은 안정성, 풍부한 기능: 네이티브 액세스 제어, 속도 제한, 민감한 단어 필터링 등의 메커니즘; 사용하기 쉽고 여러 배포 방법을 지원합니다. 여러 파이프라인 구성을 지원하며 다양한 시나리오에 대해 다른 봇을 사용할 수 있습니다.
- 🧩 플러그인 확장, 활발한 커뮤니티: 이벤트 기반, 컴포넌트 확장 등의 플러그인 메커니즘을 지원; Anthropic [MCP 프로토콜](https://modelcontextprotocol.io/) 통합; 현재 수백 개의 플러그인이 있습니다.
- 😻 웹 UI: 브라우저를 통해 LangBot 인스턴스 관리를 지원합니다. 구성 파일을 수동으로 작성할 필요가 없습니다.

더 자세한 사양은 [문서](https://docs.langbot.app/en/insight/features.html)를 참조하세요.

또는 데모 환경을 방문하세요: https://demo.langbot.dev/
  - 로그인 정보: 이메일: `demo@langbot.app` 비밀번호: `langbot123456`
  - 참고: WebUI 데모 전용이므로 공개 환경에서는 민감한 정보를 입력하지 마세요.

### 메시징 플랫폼

| 플랫폼 | 상태 | 비고 |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| 개인 QQ | ✅ |  |
| QQ 공식 API | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| WeCom AI Bot | ✅ |  |
| 개인 WeChat | ✅ |  |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### LLMs

| LLM | 상태 | 비고 |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | 모든 OpenAI 인터페이스 형식 모델에 사용 가능 |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | LLM 및 GPU 리소스 플랫폼 |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | LLM 및 GPU 리소스 플랫폼 |
| [接口 AI](https://jiekou.ai/) | ✅ | LLM 집계 플랫폼 |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | LLM 및 GPU 리소스 플랫폼 |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | LLM 게이트웨이(MaaS) |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | LLMOps 플랫폼 |
| [Ollama](https://ollama.com/) | ✅ | 로컬 LLM 실행 플랫폼 |
| [LMStudio](https://lmstudio.ai/) | ✅ | 로컬 LLM 실행 플랫폼 |
| [GiteeAI](https://ai.gitee.com/) | ✅ | LLM 인터페이스 게이트웨이(MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | LLM 게이트웨이(MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | LLM 게이트웨이(MaaS), LLMOps 플랫폼 |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | LLM 게이트웨이(MaaS), LLMOps 플랫폼 |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | LLM 게이트웨이(MaaS) |
| [MCP](https://modelcontextprotocol.io/) | ✅ | MCP 프로토콜을 통한 도구 액세스 지원 |

## 🤝 커뮤니티 기여

다음 [코드 기여자](https://github.com/langbot-app/LangBot/graphs/contributors) 및 커뮤니티의 다른 구성원들의 LangBot 기여에 감사드립니다:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

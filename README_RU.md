<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://www.producthunt.com/products/langbot?utm_source=badge-follow&utm_medium=badge&utm_source=badge-langbot" target="_blank"><img src="https://api.producthunt.com/widgets/embed-image/v1/follow.svg?product_id=1077185&theme=light" alt="LangBot - Production&#0045;grade&#0032;IM&#0032;bot&#0032;made&#0032;easy&#0046; | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" /></a>

<h3>Платформа производственного уровня для создания агентных IM-ботов.</h3>
<h4>Быстро создавайте, отлаживайте и развертывайте ИИ-ботов в Slack, Discord, Telegram, WeChat и других платформах.</h4>

[English](README.md) / [简体中文](README_CN.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / Русский / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)

<a href="https://langbot.app">Главная</a> ｜
<a href="https://docs.langbot.app/en/insight/features.html">Возможности</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">Документация</a> ｜
<a href="https://docs.langbot.app/en/tags/readme.html">API</a> ｜
<a href="https://space.langbot.app">Магазин плагинов</a> ｜
<a href="https://langbot.featurebase.app/roadmap">Дорожная карта</a>

</div>

</p>

---

## Что такое LangBot?

LangBot — это **платформа с открытым исходным кодом производственного уровня** для создания ИИ-ботов в мессенджерах. Она связывает большие языковые модели (LLM) с любой чат-платформой, позволяя создавать интеллектуальных агентов, которые могут вести диалоги, выполнять задачи и интегрироваться с вашими существующими рабочими процессами.

### Ключевые возможности

- **ИИ-диалоги и агенты** — Многораундовые диалоги, вызов инструментов, мультимодальная поддержка, потоковый вывод. Встроенная реализация RAG (база знаний) с глубокой интеграцией в [Dify](https://dify.ai), [Coze](https://coze.com), [n8n](https://n8n.io), [Langflow](https://langflow.org).
- **Универсальная поддержка IM-платформ** — Единая кодовая база для Discord, Telegram, Slack, LINE, QQ, WeChat, WeCom, Lark, DingTalk, KOOK.
- **Готовность к продакшену** — Контроль доступа, ограничение скорости, фильтрация чувствительных слов, комплексный мониторинг и обработка исключений. Проверено в корпоративной среде.
- **Экосистема плагинов** — Сотни плагинов, событийно-ориентированная архитектура, расширения компонентов и поддержка [протокола MCP](https://modelcontextprotocol.io/).
- **Веб-панель управления** — Настраивайте, управляйте и мониторьте ваших ботов через интуитивный браузерный интерфейс. Ручное редактирование YAML не требуется.
- **Мультиконвейерная архитектура** — Разные боты для разных сценариев с комплексным мониторингом и обработкой исключений.

[→ Подробнее обо всех возможностях](https://docs.langbot.app/en/insight/features.html)

---

## Быстрый старт

### ☁️ LangBot Cloud (Рекомендуется)

**[LangBot Cloud](https://space.langbot.app/cloud)** — Без развёртывания, готово к использованию.

### Запуск одной командой

```bash
uvx langbot
```

> Требуется [uv](https://docs.astral.sh/uv/getting-started/installation/). Откройте http://localhost:5300 — готово.

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

### Облачное развертывание одним кликом

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**Другие варианты:** [Docker](https://docs.langbot.app/en/deploy/langbot/docker.html) · [Ручная установка](https://docs.langbot.app/en/deploy/langbot/manual.html) · [BTPanel](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html) · [Kubernetes](./docker/README_K8S.md)

---

## Поддерживаемые платформы

| Платформа | Статус | Примечания |
|-----------|--------|------------|
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| QQ | ✅ | Личный и официальный API |
| WeCom | ✅ | Корпоративный WeChat, внешний CS, AI-бот |
| WeChat | ✅ | Личный и официальный аккаунт |
| Lark | ✅ |  |
| DingTalk | ✅ |  |
| KOOK | ✅ |  |
| Satori | ✅ |  |

---

## Поддерживаемые LLM и интеграции

| Провайдер | Тип | Статус |
|-----------|-----|--------|
| [OpenAI](https://platform.openai.com/) | LLM | ✅ |
| [Anthropic](https://www.anthropic.com/) | LLM | ✅ |
| [DeepSeek](https://www.deepseek.com/) | LLM | ✅ |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | LLM | ✅ |
| [xAI](https://x.ai/) | LLM | ✅ |
| [Moonshot](https://www.moonshot.cn/) | LLM | ✅ |
| [Zhipu AI](https://open.bigmodel.cn/) | LLM | ✅ |
| [Ollama](https://ollama.com/) | Локальный LLM | ✅ |
| [LM Studio](https://lmstudio.ai/) | Локальный LLM | ✅ |
| [Dify](https://dify.ai) | LLMOps | ✅ |
| [MCP](https://modelcontextprotocol.io/) | Протокол | ✅ |
| [SiliconFlow](https://siliconflow.cn/) | Шлюз | ✅ |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | Шлюз | ✅ |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | Шлюз | ✅ |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | Шлюз | ✅ |
| [GiteeAI](https://ai.gitee.com/) | Шлюз | ✅ |
| [302.AI](https://share.302.ai/SuTG99) | Шлюз | ✅ |
| [接口 AI](https://jiekou.ai/) | Шлюз | ✅ |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | Платформа GPU | ✅ |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | Платформа GPU | ✅ |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | Платформа GPU | ✅ |

[→ Смотреть все интеграции](https://docs.langbot.app/en/insight/features.html)

---

## Почему LangBot?

| Сценарий использования | Как помогает LangBot |
|------------------------|----------------------|
| **Поддержка клиентов** | Разверните ИИ-агентов в Slack/Discord/Telegram, которые отвечают на вопросы, используя вашу базу знаний |
| **Внутренние инструменты** | Подключите рабочие процессы n8n/Dify к WeCom/DingTalk для автоматизации бизнес-процессов |
| **Управление сообществом** | Модерируйте группы QQ/Discord с помощью ИИ-фильтрации контента и взаимодействия |
| **Мультиплатформенное присутствие** | Один бот — все платформы. Управляйте из единой панели |

---

## Демо

**Попробуйте прямо сейчас:** https://demo.langbot.dev/
- Email: `demo@langbot.app`
- Пароль: `langbot123456`

*Примечание: Публичная демо-среда. Не вводите конфиденциальную информацию.*

---

## Сообщество

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)

- [Сообщество Discord](https://discord.gg/wdNEHETs87)

---

## История Stars

[![Star History Chart](https://api.star-history.com/svg?repos=langbot-app/LangBot&type=Date)](https://star-history.com/#langbot-app/LangBot&Date)

---

## Участники

Спасибо всем [участникам](https://github.com/langbot-app/LangBot/graphs/contributors), которые помогли сделать LangBot лучше:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

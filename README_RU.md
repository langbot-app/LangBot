<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_en.png" alt="LangBot"/>
</a>

<div align="center">

[English](README_EN.md) / [简体中文](README.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / [Français](README_FR.md) / [한국어](README_KO.md) / Русский / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

<a href="https://langbot.app">Главная</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">Развертывание</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">Плагин</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">Отправить плагин</a>

</div>

</p>

LangBot — это платформа разработки ботов для мгновенных сообщений на основе LLM с открытым исходным кодом, целью которой является предоставление готового к использованию опыта разработки ботов для IM, с функциями приложений LLM, такими как Agent, RAG, MCP, адаптацией к глобальным платформам мгновенных сообщений и предоставлением богатых API-интерфейсов, поддерживающих пользовательскую разработку.

## 📦 Начало работы

#### Быстрый старт

Используйте `uvx` для запуска одной командой (требуется установка [uv](https://docs.astral.sh/uv/getting-started/installation/)):

```bash
uvx langbot
```

Посетите http://localhost:5300, чтобы начать использование.

#### Развертывание с Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

Посетите http://localhost:5300, чтобы начать использование.

Подробная документация [Развертывание Docker](https://docs.langbot.app/en/deploy/langbot/docker.html).

#### Развертывание одним кликом на BTPanel

LangBot добавлен в BTPanel. Если у вас установлен BTPanel, вы можете использовать [документацию](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html) для его использования.

#### Облачное развертывание Zeabur

Шаблон Zeabur, предоставленный сообществом.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Облачное развертывание Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### Другие методы развертывания

Используйте выпущенную версию напрямую для запуска, см. документацию [Ручное развертывание](https://docs.langbot.app/en/deploy/langbot/manual.html).

#### Развертывание Kubernetes

См. документацию [Развертывание Kubernetes](./docker/README_K8S.md).

## 😎 Оставайтесь в курсе

Нажмите кнопки Star и Watch в правом верхнем углу репозитория, чтобы получать последние обновления.

![star gif](https://docs.langbot.app/star.gif)

## ✨ Функции

- 💬 Чат с LLM / Agent: Поддержка нескольких LLM, адаптация к групповым и личным чатам; Поддержка многораундовых разговоров, вызовов инструментов, мультимодальных возможностей и потоковой передачи. Встроенная реализация RAG (база знаний) и глубокая интеграция с [Dify](https://dify.ai).
- 🤖 Многоплатформенная поддержка: В настоящее время поддерживает QQ, QQ Channel, WeCom, личный WeChat, Lark, DingTalk, Discord, Telegram и т.д.
- 🛠️ Высокая стабильность, богатство функций: Нативный контроль доступа, ограничение скорости, фильтрация чувствительных слов и т.д.; Простота в использовании, поддержка нескольких методов развертывания. Поддержка нескольких конфигураций конвейера, разные боты для разных сценариев.
- 🧩 Расширение плагинов, активное сообщество: Поддержка механизмов плагинов, управляемых событиями, расширения компонентов и т.д.; Интеграция протокола [MCP](https://modelcontextprotocol.io/) от Anthropic; В настоящее время сотни плагинов.
- 😻 Веб-интерфейс: Поддержка управления экземплярами LangBot через браузер. Нет необходимости вручную писать конфигурационные файлы.

Для более подробных спецификаций обратитесь к [документации](https://docs.langbot.app/en/insight/features.html).

Или посетите демонстрационную среду: https://demo.langbot.dev/
  - Информация для входа: Email: `demo@langbot.app` Пароль: `langbot123456`
  - Примечание: Только для демонстрации WebUI, пожалуйста, не вводите конфиденциальную информацию в общедоступной среде.

### Платформы обмена сообщениями

| Платформа | Статус | Примечания |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| Личный QQ | ✅ |  |
| Официальный API QQ | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| WeCom AI Bot | ✅ |  |
| Личный WeChat | ✅ |  |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### LLMs

| LLM | Статус | Примечания |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | Доступна для любой модели формата интерфейса OpenAI |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | Платформа ресурсов LLM и GPU |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | Платформа ресурсов LLM и GPU |
| [接口 AI](https://jiekou.ai/) | ✅ | Платформа агрегации LLM |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | Платформа ресурсов LLM и GPU |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | Шлюз LLM (MaaS) |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | Платформа LLMOps |
| [Ollama](https://ollama.com/) | ✅ | Платформа локального запуска LLM |
| [LMStudio](https://lmstudio.ai/) | ✅ | Платформа локального запуска LLM |
| [GiteeAI](https://ai.gitee.com/) | ✅ | Шлюз интерфейса LLM (MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | Шлюз LLM (MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | Шлюз LLM (MaaS), платформа LLMOps |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | Шлюз LLM (MaaS), платформа LLMOps |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | Шлюз LLM (MaaS) |
| [MCP](https://modelcontextprotocol.io/) | ✅ | Поддержка доступа к инструментам через протокол MCP |

## 🤝 Вклад сообщества

Спасибо следующим [контрибьюторам кода](https://github.com/langbot-app/LangBot/graphs/contributors) и другим членам сообщества за их вклад в LangBot:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

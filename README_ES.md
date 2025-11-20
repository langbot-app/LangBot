<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_en.png" alt="LangBot"/>
</a>

<div align="center">

[English](README_EN.md) / [简体中文](README.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / Español / [Français](README_FR.md) / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

<a href="https://langbot.app">Inicio</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">Despliegue</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">Plugin</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">Enviar Plugin</a>

</div>

</p>

LangBot es una plataforma de desarrollo de robots de mensajería instantánea nativa de LLM de código abierto, con el objetivo de proporcionar una experiencia de desarrollo de robots de mensajería instantánea lista para usar, con funciones de aplicación LLM como Agent, RAG, MCP, adaptándose a plataformas de mensajería instantánea globales y proporcionando interfaces API ricas, compatible con desarrollo personalizado.

## 📦 Comenzar

#### Inicio Rápido

Use `uvx` para iniciar con un comando (necesita instalar [uv](https://docs.astral.sh/uv/getting-started/installation/)):

```bash
uvx langbot
```

Visite http://localhost:5300 para comenzar a usarlo.

#### Despliegue con Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

Visite http://localhost:5300 para comenzar a usarlo.

Documentación detallada [Despliegue con Docker](https://docs.langbot.app/en/deploy/langbot/docker.html).

#### Despliegue con un clic en BTPanel

LangBot ha sido listado en BTPanel. Si tiene BTPanel instalado, puede usar la [documentación](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html) para usarlo.

#### Despliegue en la Nube Zeabur

Plantilla de Zeabur contribuida por la comunidad.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Despliegue en la Nube Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### Otros Métodos de Despliegue

Use directamente la versión publicada para ejecutar, consulte la documentación de [Despliegue Manual](https://docs.langbot.app/en/deploy/langbot/manual.html).

#### Despliegue en Kubernetes

Consulte la documentación de [Despliegue en Kubernetes](./docker/README_K8S.md).

## 😎 Manténgase Actualizado

Haga clic en los botones Star y Watch en la esquina superior derecha del repositorio para obtener las últimas actualizaciones.

![star gif](https://docs.langbot.app/star.gif)

## ✨ Características

- 💬 Chat con LLM / Agent: Compatible con múltiples LLMs, adaptado para chats grupales y privados; Admite conversaciones de múltiples rondas, llamadas a herramientas, capacidades multimodales y de salida en streaming. Implementación RAG (base de conocimientos) incorporada, e integración profunda con [Dify](https://dify.ai).
- 🤖 Soporte Multiplataforma: Actualmente compatible con QQ, QQ Channel, WeCom, WeChat personal, Lark, DingTalk, Discord, Telegram, etc.
- 🛠️ Alta Estabilidad, Rico en Funciones: Control de acceso nativo, limitación de velocidad, filtrado de palabras sensibles, etc.; Fácil de usar, admite múltiples métodos de despliegue. Compatible con múltiples configuraciones de pipeline, diferentes bots para diferentes escenarios.
- 🧩 Extensión de Plugin, Comunidad Activa: Compatible con mecanismos de plugin impulsados por eventos, extensión de componentes, etc.; Integración del protocolo [MCP](https://modelcontextprotocol.io/) de Anthropic; Actualmente cuenta con cientos de plugins.
- 😻 Interfaz Web: Admite la gestión de instancias de LangBot a través del navegador. No es necesario escribir archivos de configuración manualmente.

Para especificaciones más detalladas, consulte la [documentación](https://docs.langbot.app/en/insight/features.html).

O visite el entorno de demostración: https://demo.langbot.dev/
  - Información de inicio de sesión: Correo electrónico: `demo@langbot.app` Contraseña: `langbot123456`
  - Nota: Solo para demostración de WebUI, por favor no ingrese información confidencial en el entorno público.

### Plataformas de Mensajería

| Plataforma | Estado | Observaciones |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| QQ Personal | ✅ |  |
| QQ API Oficial | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| WeCom AI Bot | ✅ |  |
| WeChat Personal | ✅ |  |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### LLMs

| LLM | Estado | Observaciones |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | Disponible para cualquier modelo con formato de interfaz OpenAI |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | Plataforma de recursos LLM y GPU |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | Plataforma de recursos LLM y GPU |
| [接口 AI](https://jiekou.ai/) | ✅ | Plataforma de agregación LLM |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | Plataforma de recursos LLM y GPU |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | Gateway LLM (MaaS) |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | Plataforma LLMOps |
| [Ollama](https://ollama.com/) | ✅ | Plataforma de ejecución de LLM local |
| [LMStudio](https://lmstudio.ai/) | ✅ | Plataforma de ejecución de LLM local |
| [GiteeAI](https://ai.gitee.com/) | ✅ | Gateway de interfaz LLM (MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | Gateway LLM (MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | Gateway LLM (MaaS), plataforma LLMOps |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | Gateway LLM (MaaS), plataforma LLMOps |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | Gateway LLM (MaaS) |
| [MCP](https://modelcontextprotocol.io/) | ✅ | Compatible con acceso a herramientas a través del protocolo MCP |

## 🤝 Contribución de la Comunidad

Gracias a los siguientes [contribuidores de código](https://github.com/langbot-app/LangBot/graphs/contributors) y otros miembros de la comunidad por sus contribuciones a LangBot:

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

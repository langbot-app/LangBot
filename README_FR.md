<p align="center">
<a href="https://langbot.app">
<img src="https://docs.langbot.app/social_en.png" alt="LangBot"/>
</a>

<div align="center">

[English](README_EN.md) / [简体中文](README.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / Français / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">

<a href="https://langbot.app">Accueil</a> ｜
<a href="https://docs.langbot.app/en/insight/guide.html">Déploiement</a> ｜
<a href="https://docs.langbot.app/en/plugin/plugin-intro.html">Plugin</a> ｜
<a href="https://github.com/langbot-app/LangBot/issues/new?assignees=&labels=%E7%8B%AC%E7%AB%8B%E6%8F%92%E4%BB%B6&projects=&template=submit-plugin.yml&title=%5BPlugin%5D%3A+%E8%AF%B7%E6%B1%82%E7%99%BB%E8%AE%B0%E6%96%B0%E6%8F%92%E4%BB%B6">Soumettre un Plugin</a>

</div>

</p>

LangBot est une plateforme de développement de robots de messagerie instantanée native LLM open source, visant à fournir une expérience de développement de robots de messagerie instantanée prête à l'emploi, avec des fonctionnalités d'application LLM telles qu'Agent, RAG, MCP, s'adaptant aux plateformes de messagerie instantanée mondiales et fournissant des interfaces API riches, prenant en charge le développement personnalisé.

## 📦 Commencer

#### Démarrage Rapide

Utilisez `uvx` pour démarrer avec une commande (besoin d'installer [uv](https://docs.astral.sh/uv/getting-started/installation/)) :

```bash
uvx langbot
```

Visitez http://localhost:5300 pour commencer à l'utiliser.

#### Déploiement avec Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose up -d
```

Visitez http://localhost:5300 pour commencer à l'utiliser.

Documentation détaillée [Déploiement Docker](https://docs.langbot.app/en/deploy/langbot/docker.html).

#### Déploiement en un clic sur BTPanel

LangBot a été répertorié sur BTPanel. Si vous avez installé BTPanel, vous pouvez utiliser la [documentation](https://docs.langbot.app/en/deploy/langbot/one-click/bt.html) pour l'utiliser.

#### Déploiement Cloud Zeabur

Modèle Zeabur contribué par la communauté.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)

#### Déploiement Cloud Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

#### Autres Méthodes de Déploiement

Utilisez directement la version publiée pour exécuter, consultez la documentation de [Déploiement Manuel](https://docs.langbot.app/en/deploy/langbot/manual.html).

#### Déploiement Kubernetes

Consultez la documentation de [Déploiement Kubernetes](./docker/README_K8S.md).

## 😎 Restez à Jour

Cliquez sur les boutons Star et Watch dans le coin supérieur droit du dépôt pour obtenir les dernières mises à jour.

![star gif](https://docs.langbot.app/star.gif)

## ✨ Fonctionnalités

- 💬 Chat avec LLM / Agent : Prend en charge plusieurs LLM, adapté aux chats de groupe et privés ; Prend en charge les conversations multi-tours, les appels d'outils, les capacités multimodales et de sortie en streaming. Implémentation RAG (base de connaissances) intégrée, et intégration profonde avec [Dify](https://dify.ai).
- 🤖 Support Multi-plateforme : Actuellement compatible avec QQ, QQ Channel, WeCom, WeChat personnel, Lark, DingTalk, Discord, Telegram, etc.
- 🛠️ Haute Stabilité, Riche en Fonctionnalités : Contrôle d'accès natif, limitation de débit, filtrage de mots sensibles, etc. ; Facile à utiliser, prend en charge plusieurs méthodes de déploiement. Prend en charge plusieurs configurations de pipeline, différents bots pour différents scénarios.
- 🧩 Extension de Plugin, Communauté Active : Prend en charge les mécanismes de plugin pilotés par événements, l'extension de composants, etc. ; Intégration du protocole [MCP](https://modelcontextprotocol.io/) d'Anthropic ; Dispose actuellement de centaines de plugins.
- 😻 Interface Web : Prend en charge la gestion des instances LangBot via le navigateur. Pas besoin d'écrire manuellement les fichiers de configuration.

Pour des spécifications plus détaillées, veuillez consulter la [documentation](https://docs.langbot.app/en/insight/features.html).

Ou visitez l'environnement de démonstration : https://demo.langbot.dev/
  - Informations de connexion : Email : `demo@langbot.app` Mot de passe : `langbot123456`
  - Note : Pour la démonstration WebUI uniquement, veuillez ne pas entrer d'informations sensibles dans l'environnement public.

### Plateformes de Messagerie

| Plateforme | Statut | Remarques |
| --- | --- | --- |
| Discord | ✅ |  |
| Telegram | ✅ |  |
| Slack | ✅ |  |
| LINE | ✅ |  |
| QQ Personnel | ✅ |  |
| API Officielle QQ | ✅ |  |
| WeCom | ✅ |  |
| WeComCS | ✅ |  |
| WeCom AI Bot | ✅ |  |
| WeChat Personnel | ✅ |  |
| Lark | ✅ |  |
| DingTalk | ✅ |  |

### LLMs

| LLM | Statut | Remarques |
| --- | --- | --- |
| [OpenAI](https://platform.openai.com/) | ✅ | Disponible pour tout modèle au format d'interface OpenAI |
| [DeepSeek](https://www.deepseek.com/) | ✅ |  |
| [Moonshot](https://www.moonshot.cn/) | ✅ |  |
| [Anthropic](https://www.anthropic.com/) | ✅ |  |
| [xAI](https://x.ai/) | ✅ |  |
| [Zhipu AI](https://open.bigmodel.cn/) | ✅ |  |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | ✅ | Plateforme de ressources LLM et GPU |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | ✅ | Plateforme de ressources LLM et GPU |
| [接口 AI](https://jiekou.ai/) | ✅ | Plateforme d'agrégation LLM |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | ✅ | Plateforme de ressources LLM et GPU |
| [302.AI](https://share.302.ai/SuTG99) | ✅ | Passerelle LLM (MaaS) |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | ✅ | |
| [Dify](https://dify.ai) | ✅ | Plateforme LLMOps |
| [Ollama](https://ollama.com/) | ✅ | Plateforme d'exécution LLM locale |
| [LMStudio](https://lmstudio.ai/) | ✅ | Plateforme d'exécution LLM locale |
| [GiteeAI](https://ai.gitee.com/) | ✅ | Passerelle d'interface LLM (MaaS) |
| [SiliconFlow](https://siliconflow.cn/) | ✅ | Passerelle LLM (MaaS) |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | ✅ | Passerelle LLM (MaaS), plateforme LLMOps |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | ✅ | Passerelle LLM (MaaS), plateforme LLMOps |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | ✅ | Passerelle LLM (MaaS) |
| [MCP](https://modelcontextprotocol.io/) | ✅ | Prend en charge l'accès aux outils via le protocole MCP |

## 🤝 Contribution de la Communauté

Merci aux [contributeurs de code](https://github.com/langbot-app/LangBot/graphs/contributors) suivants et aux autres membres de la communauté pour leurs contributions à LangBot :

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

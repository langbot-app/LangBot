<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://www.producthunt.com/products/langbot/launches/langbot?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-langbot" target="_blank" rel="noopener noreferrer"><img alt="LangBot - Easy-to-use global IM bot platform designed for the LLM era | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=979554&amp;theme=light&amp;t=1782822143403"></a>

<h3>Des bots IA au service de vos communautés, clients et équipes.</h3>
<h4>Partez d'un scénario prêt à l'emploi ou connectez votre app Dify / n8n / Coze, et faites-la tourner de manière fiable sur WeChat, QQ, Slack, Discord, Telegram et plus.</h4>

[English](README.md) / [简体中文](README_CN.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / Français / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)

<a href="https://langbot.app">Accueil</a> ｜
<a href="https://langbot.app/docs/en/insight/features">Fonctionnalités</a> ｜
<a href="https://langbot.app/docs/en/insight/guide">Documentation</a> ｜
<a href="https://langbot.app/docs/en/tags/readme">API</a> ｜
<a href="https://space.langbot.app">Marché des Plugins</a> ｜
<a href="https://langbot.featurebase.app/roadmap">Feuille de Route</a>

</div>

</p>

---

## Qu'est-ce que LangBot ?

LangBot est une **plateforme open-source de bots de messagerie** conçue pour les bots qui servent beaucoup de monde : discussions de groupe et communautés, relation client sur WeChat et WeCom, assistants internes sur Lark, DingTalk ou Slack. Partez d'un scénario prêt à l'emploi, ou apportez l'app IA que vous avez déjà construite sur Dify, n8n ou Coze. Gérez tous vos groupes et plateformes depuis un seul tableau de bord, avec des journaux quand quelque chose ne va pas.

<p align="center">
<img src="res/dashboard-overview.png" alt="Tableau de bord de gestion web LangBot — surveillance en temps réel du volume de messages, des appels de modèles, du taux de réussite et des sessions actives" width="720"/>
</p>

### Capacités Clés

- **Un bot, tous les groupes et plateformes** — QQ, WeChat, WeCom, Lark, DingTalk, Discord, Telegram, Slack, LINE, KOOK et plus. Des bots et pipelines différents pour chaque groupe et scénario, gérés depuis un seul endroit.
- **Conçu pour les groupes et le service client** — Règles de déclenchement en groupe, isolation des sessions, limitation de débit, filtrage de mots sensibles, accueil des nouveaux membres, gestion des demandes d'ami et transfert vers un humain via plugin.
- **Conversations IA & Agents** — Dialogues multi-tours, appels d'outils, support multimodal, sortie en streaming. RAG (base de connaissances) intégré avec intégration profonde de [Dify](https://dify.ai), [Coze](https://coze.com), [n8n](https://n8n.io), [Langflow](https://langflow.org), [Deerflow](https://deerflow.tech), [Weknora](https://weknora.weixin.qq.com).
- **Fiable et facile à diagnostiquer** — Contrôle d'accès, journaux d'exécution complets, historique des appels, gestion des exceptions et export des données. Au service de nombreux environnements de production.
- **Écosystème de Plugins** — Des centaines de plugins, serveurs MCP et Skills, installables en un clic depuis la marketplace. Architecture événementielle et extensions de composants.
- **Panneau de Gestion Web** — Configurez, gérez et surveillez vos bots via une interface navigateur intuitive. Aucune édition de YAML requise.

[→ En savoir plus sur toutes les fonctionnalités](https://langbot.app/docs/en/insight/features)

📍 Guides pratiques : [déployer un bot IA multiplateforme en 5 minutes](https://langbot.app/en/blog/deploy-ai-bot-in-5-minutes/), [connecter DeepSeek à WeChat, Discord et Telegram](https://langbot.app/en/blog/connect-deepseek-to-wechat/), [exécuter un Dify Agent dans Discord, Telegram et Slack](https://langbot.app/en/blog/dify-agent-discord-telegram-slack/) et [créer un chatbot avec n8n](https://langbot.app/en/blog/n8n-multi-platform-ai-chatbot/).

---

## 😎 Restez à Jour

Cliquez sur les boutons Star et Watch dans le coin supérieur droit du dépôt pour obtenir les dernières mises à jour.

![star gif](https://langbot.app/star.gif)

## Démarrage Rapide

### ☁️ LangBot Cloud (Recommandé)

[![Deploy on LangBot Cloud](res/langbot-cloud.svg)](https://cloud.langbot.app)

[cloud.langbot.app](https://cloud.langbot.app)

Sans déploiement, prêt à utiliser.

### Lancement en une ligne

```bash
uvx langbot
```

> Nécessite [uv](https://docs.astral.sh/uv/getting-started/installation/). Visitez http://localhost:5300 — c'est prêt.

### Docker Compose

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker
docker compose --profile all up -d
```


### Déploiement Cloud en un Clic

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/en-US/templates/ZKTBDH)
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/template/yRrAyL?referralCode=vogKPF)

**Plus d'options :** [Docker](https://langbot.app/docs/en/deploy/langbot/docker) · [Manuel](https://langbot.app/docs/en/deploy/langbot/manual) · [BTPanel](https://langbot.app/docs/en/deploy/langbot/one-click/bt) · [Kubernetes](https://langbot.app/docs/en/deploy/langbot/kubernetes)

---

## Plateformes Supportées

| Plateforme | Statut | Notes |
|----------|--------|-------|
| Discord | ✅ | Officiel |
| Telegram | ✅ | Officiel |
| Slack | ✅ | Officiel |
| LINE | ✅ | Officiel |
| QQ | ✅ | Personnel & API Officielle (Canal, DM, Groupe) |
| WeCom | ✅ | WeChat Entreprise, CS Externe, AI Bot |
| WeChat | ✅ | Personnel & Compte Officiel |
| Lark | ✅ | Officiel |
| DingTalk | ✅ | Officiel |
| KOOK | ✅ | Officiel |
| Satori | ✅ |  |
| Email | ✅ | Matrix, Satori |
| Matrix | ✅ | Prend en charge plusieurs plateformes via ponts, comme Signal, WhatsApp, Messenger, iMessage, Mattermost, Google Chat, IRC, XMPP, Zulip, etc. |

---

## LLMs et Intégrations Supportés

| Fournisseur | Type | Statut |
|----------|------|--------|
| [OpenAI](https://platform.openai.com/) | LLM | ✅ |
| [Anthropic](https://www.anthropic.com/) | LLM | ✅ |
| [DeepSeek](https://www.deepseek.com/) | LLM | ✅ |
| [Google Gemini](https://aistudio.google.com/prompts/new_chat) | LLM | ✅ |
| [xAI](https://x.ai/) | LLM | ✅ |
| [Moonshot](https://www.moonshot.cn/) | LLM | ✅ |
| [Zhipu AI](https://open.bigmodel.cn/) | LLM | ✅ |
| [Ollama](https://ollama.com/) | LLM Local | ✅ |
| [LM Studio](https://lmstudio.ai/) | LLM Local | ✅ |
| [Dify](https://dify.ai) | LLMOps | ✅ |
| [MCP](https://modelcontextprotocol.io/) | Protocole | ✅ |
| [SiliconFlow](https://siliconflow.cn/) | Passerelle | ✅ |
| [Aliyun Bailian](https://bailian.console.aliyun.com/) | Passerelle | ✅ |
| [Volc Engine Ark](https://console.volcengine.com/ark/region:ark+cn-beijing/model?vendor=Bytedance&view=LIST_VIEW) | Passerelle | ✅ |
| [ModelScope](https://modelscope.cn/docs/model-service/API-Inference/intro) | Passerelle | ✅ |
| [GiteeAI](https://ai.gitee.com/) | Passerelle | ✅ |
| [接口 AI](https://jiekou.ai/) | Passerelle | ✅ |
| [302.AI](https://share.302ai.cn/SuTG99) | Passerelle | ✅ |
| [CompShare](https://www.compshare.cn/?ytag=GPU_YY-gh_langbot) | Plateforme GPU | ✅ |
| [PPIO](https://ppinfra.com/user/register?invited_by=QJKFYD&utm_source=github_langbot) | Plateforme GPU | ✅ |
| [ShengSuanYun](https://www.shengsuanyun.com/?from=CH_KYIPP758) | Plateforme GPU | ✅ |
| [Qiniu](https://www.qiniu.com/ai/agent) | Passerelle | ✅ |

[→ Voir toutes les intégrations](https://langbot.app/docs/en/insight/features)

---

## Pourquoi LangBot ?

| Cas d'Usage | Comment LangBot Aide |
| --- | --- |
| **Bots de communauté** | Répondez aux questions, accueillez les nouveaux membres et interagissez selon vos règles dans les groupes QQ / Discord / Telegram, en gardant le contexte de chaque membre |
| **Canaux privés et service client** | Répondez automatiquement aux demandes sur WeChat et le service client WeCom avec votre base de connaissances, avec transfert vers un humain si besoin |
| **Votre app IA dans la messagerie** | Connectez vos apps Dify / n8n / Coze à n'importe quelle plateforme de chat en une étape, sans code d'intégration |
| **Assistants d'équipe** | Q&R sur la base de connaissances et automatisation des processus dans Lark, DingTalk et WeCom, gérés en équipe |

---

## Conçu pour les agents IA 🤖

LangBot est **agent-friendly par conception** —— vos agents de codage (Claude Code, Codex, Copilot, Cursor, …) peuvent exploiter, étendre et déployer LangBot avec un support de premier ordre :

- **Serveur MCP** —— LangBot expose un endpoint [Model Context Protocol](https://modelcontextprotocol.io/) intégré sur `/mcp`, reflétant l'API HTTP pour qu'un agent gère bots, pipelines, plugins et modèles de façon programmatique. Authentifiez-vous avec la même clé API (définissez une clé globale dans `config.yaml` ou utilisez une clé par utilisateur) —— sans flux de connexion. Configurez-le dans l'onglet **API & MCP** du panneau web.
- **Skills dans le dépôt** —— Le répertoire [`skills/`](skills/) est la **source unique de vérité** pour travailler avec LangBot : développement de plugins, développement du cœur, tests de bout en bout, déploiement et exploitation des serveurs MCP de LangBot / LangBot Space. Pointez votre agent vers ce répertoire et il saura construire.
- **AGENTS.md** —— Chaque dépôt fournit un [`AGENTS.md`](AGENTS.md) (lien symbolique vers `CLAUDE.md`) décrivant l'architecture, les conventions et la règle selon laquelle les changements d'API doivent garder le serveur MCP et les skills synchronisés.
- **`llms.txt`** —— Le contexte projet lisible par machine pour les LLM est publié sur le site web.

> **Cloud / Marketplace :** [LangBot Space](https://space.langbot.app) expose également un serveur MCP pour que les agents recherchent et inspectent le marketplace de plugins / MCP / skills, authentifiés avec un Personal Access Token.

---

## Communauté

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&label=Discord)](https://discord.gg/wdNEHETs87)

- [Communauté Discord](https://discord.gg/wdNEHETs87)

---

## Contributeurs

Merci à tous les [contributeurs](https://github.com/langbot-app/LangBot/graphs/contributors) qui ont aidé à améliorer LangBot :

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

[Sources de la documentation](https://github.com/langbot-app/LangBot/tree/master/docs) · [langbot-docs archive](https://github.com/langbot-app/langbot-docs)

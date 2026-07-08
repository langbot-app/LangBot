<p align="center">
<a href="https://langbot.app">
<img width="130" src="res/logo-blue.png" alt="LangBot"/>
</a>

<div align="center">

<a href="https://www.producthunt.com/products/langbot/launches/langbot?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-langbot" target="_blank" rel="noopener noreferrer"><img alt="LangBot - Easy-to-use global IM bot platform designed for the LLM era | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=979554&amp;theme=light&amp;t=1782822143403"></a>

<h3>Plateforme de niveau production pour construire des bots de messagerie instantanée avec agents IA.</h3>
<h4>Créez, déboguez et déployez rapidement des bots IA sur Slack, Discord, Telegram, WeChat et plus.</h4>

[English](README.md) / [简体中文](README_CN.md) / [繁體中文](README_TW.md) / [日本語](README_JP.md) / [Español](README_ES.md) / Français / [한국어](README_KO.md) / [Русский](README_RU.md) / [Tiếng Việt](README_VI.md)

[![Discord](https://img.shields.io/discord/1335141740050649118?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb)](https://discord.gg/wdNEHETs87)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langbot-app/LangBot)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/langbot-app/LangBot)](https://github.com/langbot-app/LangBot/releases/latest)
<img src="https://img.shields.io/badge/python-3.10 ~ 3.13 -blue.svg" alt="python">
[![GitHub stars](https://img.shields.io/github/stars/langbot-app/LangBot?style=social)](https://github.com/langbot-app/LangBot/stargazers)

<a href="https://langbot.app">Accueil</a> ｜
<a href="https://link.langbot.app/en/docs/features">Fonctionnalités</a> ｜
<a href="https://link.langbot.app/en/docs/guide">Documentation</a> ｜
<a href="https://link.langbot.app/en/docs/api">API</a> ｜
<a href="https://space.langbot.app">Marché des Plugins</a> ｜
<a href="https://langbot.featurebase.app/roadmap">Feuille de Route</a>

</div>

</p>

---

## Qu'est-ce que LangBot ?

LangBot est une **plateforme open-source de niveau production** pour créer des bots de messagerie instantanée alimentés par l'IA. Elle connecte les grands modèles de langage (LLMs) à n'importe quelle plateforme de chat, vous permettant de créer des agents intelligents capables de converser, d'exécuter des tâches et de s'intégrer à vos workflows existants.

<p align="center">
<img src="res/dashboard-overview.png" alt="Tableau de bord de gestion web LangBot — surveillance en temps réel du volume de messages, des appels de modèles, du taux de réussite et des sessions actives" width="720"/>
</p>

### Capacités Clés

- **Conversations IA & Agents** — Dialogues multi-tours, appels d'outils, support multimodal, sortie en streaming. RAG (base de connaissances) intégré avec intégration profonde de [Dify](https://dify.ai), [Coze](https://coze.com), [n8n](https://n8n.io), [Langflow](https://langflow.org), [Deerflow](https://deerflow.tech), [Weknora](https://weknora.weixin.qq.com).
- **Support Universel des Plateformes de MI** — Un seul code pour Discord, Telegram, Slack, LINE, QQ, WeChat, WeCom, Lark, DingTalk, KOOK.
- **Prêt pour la Production** — Contrôle d'accès, limitation de débit, filtrage de mots sensibles, surveillance complète et gestion des exceptions. Approuvé par les entreprises.
- **Écosystème de Plugins** — Des centaines de plugins, architecture événementielle, extensions de composants, et support du [protocole MCP](https://modelcontextprotocol.io/).
- **Panneau de Gestion Web** — Configurez, gérez et surveillez vos bots via une interface navigateur intuitive. Aucune édition de YAML requise.
- **Architecture Multi-Pipeline** — Différents bots pour différents scénarios, avec surveillance complète et gestion des exceptions.

[→ En savoir plus sur toutes les fonctionnalités](https://link.langbot.app/en/docs/features)

📍 Guides pratiques : [déployer un bot IA multiplateforme en 5 minutes](https://blog.langbot.app/en/blog/deploy-ai-bot-in-5-minutes/), [connecter DeepSeek à WeChat, Discord et Telegram](https://blog.langbot.app/en/blog/connect-deepseek-to-wechat/), [exécuter un Dify Agent dans Discord, Telegram et Slack](https://blog.langbot.app/en/blog/dify-agent-discord-telegram-slack/) et [créer un chatbot avec n8n](https://blog.langbot.app/en/blog/n8n-multi-platform-ai-chatbot/).

---

## 😎 Restez à Jour

Cliquez sur les boutons Star et Watch dans le coin supérieur droit du dépôt pour obtenir les dernières mises à jour.

![star gif](https://langbot.app/star.gif)

## Démarrage Rapide

### ☁️ LangBot Cloud (Recommandé)

**[LangBot Cloud](https://space.langbot.app/cloud)** — Sans déploiement, prêt à utiliser.

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

**Plus d'options :** [Docker](https://link.langbot.app/en/docs/docker) · [Manuel](https://link.langbot.app/en/docs/manual-deploy) · [BTPanel](https://link.langbot.app/en/docs/bt-panel) · [Kubernetes](https://docs.langbot.app/en/deploy/langbot/kubernetes)

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

[→ Voir toutes les intégrations](https://link.langbot.app/en/docs/features)

---

## Pourquoi LangBot ?

| Cas d'Usage | Comment LangBot Aide |
|----------|-------------------|
| **Support Client** | Déployez des agents IA sur Slack/Discord/Telegram qui répondent aux questions en utilisant votre base de connaissances |
| **Outils Internes** | Connectez les workflows n8n/Dify à WeCom/DingTalk pour automatiser vos processus métier |
| **Gestion de Communauté** | Modérez les groupes QQ/Discord avec un filtrage de contenu et des interactions alimentés par l'IA |
| **Présence Multi-plateforme** | Un seul bot, toutes les plateformes. Gérez tout depuis un tableau de bord unique |

---

## Démo en Ligne

**Essayez maintenant :** https://demo.langbot.dev/
- Email : `demo@langbot.app`
- Mot de passe : `langbot123456`

*Note : Environnement de démonstration public. Ne saisissez pas d'informations sensibles.*

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

## Historique des Stars

[![Star History Chart](https://api.star-history.com/svg?repos=langbot-app/LangBot&type=Date)](https://star-history.com/#langbot-app/LangBot&Date)

---

## Contributeurs

Merci à tous les [contributeurs](https://github.com/langbot-app/LangBot/graphs/contributors) qui ont aidé à améliorer LangBot :

<a href="https://github.com/langbot-app/LangBot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=langbot-app/LangBot" />
</a>

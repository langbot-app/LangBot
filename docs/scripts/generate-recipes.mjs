#!/usr/bin/env node
// Generates the integration recipe pages ({en,zh,ja}/recipes/**) and their
// docs.json navigation from scripts/recipes-data.mjs.
//   node scripts/generate-recipes.mjs          write files
//   node scripts/generate-recipes.mjs --check  fail if generated files drift

import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { LANGS, PLATFORMS, SOURCES } from "./recipes-data.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NAV_LANGUAGE = { en: "en", zh: "cn", ja: "jp" };
const CHECK = process.argv.includes("--check");

const T = {
  en: {
    title: (s, p) => (s.kind === "model" ? `Build a ${p} AI Bot with ${s.name}` : `Connect ${s.name} to ${p}`),
    description: (s, p) =>
      s.kind === "model"
        ? `Step-by-step guide to running a ${s.name}-powered AI bot on ${p} with LangBot: model setup, bot credentials, networking, testing and troubleshooting.`
        : `Step-by-step guide to running your ${s.name} app as a ${p} bot with LangBot: ${s.name} setup, bot credentials, networking, testing and troubleshooting.`,
    intro: (s, p) => `This recipe puts ${s.kind === "model" ? `a ${s.name} model` : `your ${s.name} app`} behind a ${p} bot. LangBot receives messages from ${p}, runs them through a pipeline, and sends the answer back, so you do not write any platform code.`,
    need: "What you need",
    needLangBot: "A running LangBot instance: [LangBot Cloud](https://space.langbot.app/cloud) (no server needed) or a [self-hosted deployment](/en/deploy/langbot/docker) with Docker or `uvx langbot`.",
    needSource: (s) => (s.kind === "model" ? `A ${s.name} account or server you can call from LangBot.` : `A ${s.name} account or instance that LangBot can reach over the network.`),
    network: "Networking",
    step1: (s) => (s.kind === "model" ? `1. Add the ${s.name} model` : `1. Prepare ${s.name}`),
    step2: "2. Create a pipeline",
    step2Intro: (s) => `Open **Pipelines** in the LangBot WebUI, create a pipeline (or edit the default one) and set **AI** as follows.${s.kind === "runner" ? " If the runner is not listed, install the official runner plugin from **Plugins** or the [LangBot Space marketplace](https://space.langbot.app/market)." : ""}`,
    field: "Field", value: "Value",
    step3: (p) => `3. Create the ${p} bot`,
    step4: "4. Bind and test",
    step4Body: "Open the bot, select the pipeline you created, save and make sure the bot is enabled.",
    trouble: "Troubleshooting",
    troubleCommon: "Check **Monitoring** in the WebUI: every message, pipeline run and error is recorded there.",
    faq: "FAQ",
    faqServer: (p) => `Do I need a server with a public IP for ${p}?`,
    faqStream: (p) => `Does the ${p} bot support streaming replies?`,
    faqStreamYes: "Yes. Enable streaming on the bot; the AI back end must also stream. See the [platform feature matrix](/en/insight/platform-features) for details.",
    faqStreamNo: "Check the [platform feature matrix](/en/insight/platform-features) for what this platform supports. Replies are delivered once the AI back end has finished.",
    faqReuse: (s) => `Can the same ${s.name} setup serve other platforms too?`,
    faqReuseA: "Yes. A pipeline can be bound to many bots, so one configuration can answer on several platforms at once.",
    related: "Related guides",
    fullPlatform: (p) => `Full ${p} setup guide`,
    fullSource: (s) => (s.kind === "model" ? "Model configuration" : `Full ${s.name} runner guide`),
    samePlatform: (p) => `Other AI back ends on ${p}`,
    sameSource: (s) => `${s.name} on other platforms`,
    indexTitle: "Integration Recipes",
    indexDescription: "Short, task-focused guides for connecting Dify, n8n, Coze, Langflow, DeepSeek, OpenAI, Claude, Gemini, Qwen and Ollama to Telegram, Discord, Slack, Lark, DingTalk, WeCom, WeChat, QQ, LINE, KOOK, Mattermost and websites with LangBot.",
    indexIntro: "Each recipe covers one AI back end on one messaging platform: what to prepare, which fields to fill in, the network requirement and the usual mistakes. For the full reference, follow the links to the platform and runner guides.",
    agentPlatforms: "Agent platforms", models: "Models (built-in Agent)",
    navGroup: "Integration Recipes",
    colon: ": ",
  },
  zh: {
    title: (s, p) => (s.kind === "model" ? `用 ${s.name} 搭建${p} AI 机器人` : `把 ${s.name} 接入${p}`),
    description: (s, p) =>
      s.kind === "model"
        ? `使用 LangBot 搭建由 ${s.name} 驱动的${p} AI 机器人：模型配置、机器人凭据、网络要求、测试与常见问题。`
        : `使用 LangBot 把 ${s.name} 应用接入${p}：${s.name} 配置、机器人凭据、网络要求、测试与常见问题。`,
    intro: (s, p) => `本文把${s.kind === "model" ? ` ${s.name} 模型` : `你的 ${s.name} 应用`}接到${p}机器人上。LangBot 接收${p}消息，交给流水线处理后把答案发回去，你不需要写任何平台对接代码。`,
    need: "准备工作",
    needLangBot: "一个运行中的 LangBot：[LangBot Cloud](https://space.langbot.app/cloud)（无需服务器），或用 Docker、`uvx langbot` [自行部署](/zh/deploy/langbot/docker)。",
    needSource: (s) => (s.kind === "model" ? `可以从 LangBot 调用的 ${s.name} 账号或服务。` : `LangBot 能通过网络访问到的 ${s.name} 账号或实例。`),
    network: "网络要求",
    step1: (s) => (s.kind === "model" ? `1. 添加 ${s.name} 模型` : `1. 准备 ${s.name}`),
    step2: "2. 创建流水线",
    step2Intro: (s) => `在 LangBot WebUI 打开 **流水线**，新建流水线（或编辑默认流水线），按下表配置 **AI** 能力。${s.kind === "runner" ? "如果列表里没有对应运行器，请先在 **插件** 或 [LangBot Space 插件市场](https://space.langbot.app/market) 安装官方运行器插件。" : ""}`,
    field: "配置项", value: "填写",
    step3: (p) => `3. 创建${p}机器人`,
    step4: "4. 绑定并测试",
    step4Body: "打开机器人，选择刚才创建的流水线，保存并确认机器人已启用。",
    trouble: "常见问题排查",
    troubleCommon: "在 WebUI 的 **监控** 页面可以看到每条消息、每次流水线运行和错误详情。",
    faq: "常见问题",
    faqServer: (p) => `接入${p}需要有公网 IP 的服务器吗？`,
    faqStream: (p) => `${p}机器人支持流式回复吗？`,
    faqStreamYes: "支持。在机器人上开启流式输出，同时 AI 后端也要支持流式。详见[平台功能对照表](/zh/insight/platform-features)。",
    faqStreamNo: "请查看[平台功能对照表](/zh/insight/platform-features)了解该平台支持的能力；AI 后端生成完成后会一次性发送回复。",
    faqReuse: (s) => `同一套 ${s.name} 配置能同时用在其他平台吗？`,
    faqReuseA: "可以。一条流水线可以绑定多个机器人，同一套配置能同时在多个平台上回复。",
    related: "相关文档",
    fullPlatform: (p) => `${p}完整接入文档`,
    fullSource: (s) => (s.kind === "model" ? "模型配置" : `${s.name} 运行器完整文档`),
    samePlatform: (p) => `${p}上的其他 AI 后端`,
    sameSource: (s) => `${s.name} 接入其他平台`,
    indexTitle: "接入实例",
    indexDescription: "把 Dify、n8n、扣子、Langflow、DeepSeek、OpenAI、Claude、Gemini、通义千问、Ollama 接入 Telegram、Discord、Slack、飞书、钉钉、企业微信、微信、QQ、LINE、KOOK、Mattermost 和网页的分步教程。",
    indexIntro: "每篇只讲一个 AI 后端接入一个聊天平台：要准备什么、填哪些配置、网络要求和常见错误。需要完整说明时，可以跳转到对应的平台文档和运行器文档。",
    agentPlatforms: "智能体平台", models: "模型（内置 Agent）",
    navGroup: "接入实例",
    colon: "：",
  },
  ja: {
    title: (s, p) => (s.kind === "model" ? `${s.name} で ${p} の AI ボットを作る` : `${s.name} を ${p} に接続する`),
    description: (s, p) =>
      s.kind === "model"
        ? `LangBot で ${s.name} を使った ${p} の AI ボットを動かす手順：モデル設定、ボットの認証情報、ネットワーク、テスト、トラブルシューティング。`
        : `LangBot で ${s.name} アプリを ${p} のボットとして動かす手順：${s.name} の設定、ボットの認証情報、ネットワーク、テスト、トラブルシューティング。`,
    intro: (s, p) => `このレシピでは${s.kind === "model" ? ` ${s.name} のモデル` : `お使いの ${s.name} アプリ`}を ${p} のボットにつなぎます。LangBot が ${p} のメッセージを受け取り、パイプラインで処理して返信するので、プラットフォーム連携のコードは不要です。`,
    need: "必要なもの",
    needLangBot: "稼働中の LangBot：[LangBot Cloud](https://space.langbot.app/cloud)（サーバー不要）、または Docker や `uvx langbot` による[セルフホスト](/ja/deploy/langbot/docker)。",
    needSource: (s) => (s.kind === "model" ? `LangBot から呼び出せる ${s.name} のアカウントまたはサーバー。` : `LangBot からネットワーク経由で到達できる ${s.name} のアカウントまたはインスタンス。`),
    network: "ネットワーク",
    step1: (s) => (s.kind === "model" ? `1. ${s.name} のモデルを追加する` : `1. ${s.name} を準備する`),
    step2: "2. パイプラインを作成する",
    step2Intro: (s) => `LangBot WebUI の **パイプライン** でパイプラインを作成（または既定のものを編集）し、**AI** を次のように設定します。${s.kind === "runner" ? "ランナーが一覧にない場合は、**プラグイン** または [LangBot Space マーケット](https://space.langbot.app/market) から公式ランナープラグインをインストールします。" : ""}`,
    field: "項目", value: "設定値",
    step3: (p) => `3. ${p} のボットを作成する`,
    step4: "4. 紐付けてテストする",
    step4Body: "ボットを開いて作成したパイプラインを選び、保存してボットが有効になっていることを確認します。",
    trouble: "トラブルシューティング",
    troubleCommon: "WebUI の **モニタリング** に、すべてのメッセージ、パイプラインの実行、エラーが記録されます。",
    faq: "よくある質問",
    faqServer: (p) => `${p} には公開 IP のあるサーバーが必要ですか？`,
    faqStream: (p) => `${p} のボットはストリーミング返信に対応していますか？`,
    faqStreamYes: "はい。ボットでストリーミングを有効にし、AI 側もストリーミングに対応している必要があります。詳しくは[プラットフォーム機能一覧](/ja/insight/platform-features)をご覧ください。",
    faqStreamNo: "対応状況は[プラットフォーム機能一覧](/ja/insight/platform-features)で確認してください。AI 側の生成が終わってから返信が送られます。",
    faqReuse: (s) => `同じ ${s.name} の設定を他のプラットフォームでも使えますか？`,
    faqReuseA: "はい。1 つのパイプラインを複数のボットに紐付けられるので、同じ設定で複数のプラットフォームに同時に応答できます。",
    related: "関連ガイド",
    fullPlatform: (p) => `${p} の詳しい設定ガイド`,
    fullSource: (s) => (s.kind === "model" ? "モデルの設定" : `${s.name} ランナーの詳しいガイド`),
    samePlatform: (p) => `${p} で使える他の AI`,
    sameSource: (s) => `${s.name} を他のプラットフォームで使う`,
    indexTitle: "連携レシピ",
    indexDescription: "Dify、n8n、Coze、Langflow、DeepSeek、OpenAI、Claude、Gemini、Qwen、Ollama を Telegram、Discord、Slack、Lark、DingTalk、WeCom、WeChat、QQ、LINE、KOOK、Mattermost、Web サイトに LangBot でつなぐ手順ガイド。",
    indexIntro: "各レシピは 1 つの AI と 1 つのメッセージングプラットフォームの組み合わせだけを扱い、準備するもの、入力する項目、ネットワーク要件、よくあるミスをまとめています。詳しくはリンク先のプラットフォーム／ランナーのガイドをご覧ください。",
    agentPlatforms: "エージェント基盤", models: "モデル（内蔵エージェント）",
    navGroup: "連携レシピ",
    colon: "：",
  },
};

const yamlString = (value) => JSON.stringify(value);
const link = (lang, guide) => `/${lang}/${guide}`;
const recipePath = (lang, s, p) => `/${lang}/recipes/${s.slug}/${p.slug}`;

function serverAnswer(lang, p) {
  const base = p.networkNote[lang];
  if (p.network === "outbound") return { en: `No. ${base}`, zh: `不需要。${base}`, ja: `いいえ。${base}` }[lang];
  if (p.network === "either") return { en: `Not necessarily. ${base}`, zh: `不一定。${base}`, ja: `必ずしも必要ではありません。${base}` }[lang];
  return { en: `Yes, or use LangBot Cloud. ${base}`, zh: `需要，或者直接使用 LangBot Cloud。${base}`, ja: `必要です。または LangBot Cloud を使えます。${base}` }[lang];
}

function renderRecipe(lang, s, p) {
  const t = T[lang];
  const pName = p.name[lang];
  const fields = s.fields[lang];
  const otherSources = SOURCES.filter((x) => x.slug !== s.slug);
  const otherPlatforms = PLATFORMS.filter((x) => x.slug !== p.slug);
  const lines = [
    "---",
    `title: ${yamlString(t.title(s, pName))}`,
    `description: ${yamlString(t.description(s, pName))}`,
    "---",
    "",
    t.intro(s, pName),
    "",
    s.blurb[lang],
    "",
    `## ${t.need}`,
    "",
    `- ${t.needLangBot}`,
    `- ${t.needSource(s)}`,
    `- ${p.creds[lang]}`,
    "",
    `## ${t.network}`,
    "",
    p.networkNote[lang],
    "",
    `## ${t.step1(s)}`,
    "",
    ...s.prepare[lang].map((item, i) => `${i + 1}. ${item}`),
    "",
    `## ${t.step2}`,
    "",
    t.step2Intro(s),
    "",
    `| ${t.field} | ${t.value} |`,
    "| --- | --- |",
    ...fields.map(([field, value]) => `| ${field} | ${value} |`),
    "",
    `## ${t.step3(pName)}`,
    "",
    ...p.setup[lang].map((item, i) => `${i + 1}. ${item}`),
    "",
    `## ${t.step4}`,
    "",
    t.step4Body,
    "",
    p.test[lang],
    "",
    `## ${t.trouble}`,
    "",
    ...[...s.trouble[lang], ...p.trouble[lang], t.troubleCommon].map((item) => `- ${item}`),
    "",
    `## ${t.faq}`,
    "",
    `### ${t.faqServer(pName)}`,
    "",
    serverAnswer(lang, p),
    "",
    `### ${t.faqStream(pName)}`,
    "",
    p.streaming ? t.faqStreamYes : t.faqStreamNo,
    "",
    `### ${t.faqReuse(s)}`,
    "",
    t.faqReuseA,
    "",
    `## ${t.related}`,
    "",
    `- [${t.fullPlatform(pName)}](${link(lang, p.guide)})`,
    `- [${t.fullSource(s)}](${link(lang, s.guide)})`,
    `- ${t.samePlatform(pName)}${t.colon}${otherSources.slice(0, 5).map((x) => `[${x.name}](${recipePath(lang, x, p)})`).join(" · ")}`,
    `- ${t.sameSource(s)}${t.colon}${otherPlatforms.slice(0, 6).map((x) => `[${x.name[lang]}](${recipePath(lang, s, x)})`).join(" · ")}`,
    "",
  ];
  return lines.join("\n");
}

function renderIndex(lang) {
  const t = T[lang];
  const section = (title, sources) => [
    `## ${title}`,
    "",
    ...sources.flatMap((s) => [
      `### ${s.name}`,
      "",
      PLATFORMS.map((p) => `[${p.name[lang]}](${recipePath(lang, s, p)})`).join(" · "),
      "",
    ]),
  ];
  return [
    "---",
    `title: ${yamlString(t.indexTitle)}`,
    `description: ${yamlString(t.indexDescription)}`,
    "---",
    "",
    t.indexIntro,
    "",
    ...section(t.agentPlatforms, SOURCES.filter((s) => s.kind === "runner")),
    ...section(t.models, SOURCES.filter((s) => s.kind === "model")),
  ].join("\n");
}

function expectedFiles() {
  const files = new Map();
  for (const lang of LANGS) {
    files.set(path.join(lang, "recipes", "index.mdx"), renderIndex(lang));
    for (const s of SOURCES) {
      for (const p of PLATFORMS) files.set(path.join(lang, "recipes", s.slug, `${p.slug}.mdx`), renderRecipe(lang, s, p));
    }
  }
  return files;
}

function navGroup(lang) {
  const t = T[lang];
  return {
    group: t.navGroup,
    pages: [
      `${lang}/recipes/index`,
      ...SOURCES.map((s) => ({ group: s.name, pages: PLATFORMS.map((p) => `${lang}/recipes/${s.slug}/${p.slug}`) })),
    ],
  };
}

function isRecipeGroup(group) {
  const first = group?.pages?.[0];
  return typeof first === "string" && /^(en|zh|ja)\/recipes\/index$/.test(first);
}

function withNavigation(docs) {
  const next = structuredClone(docs);
  for (const lang of LANGS) {
    const language = next.navigation.languages.find((item) => item.language === NAV_LANGUAGE[lang]);
    if (!language) throw new Error(`docs.json has no ${NAV_LANGUAGE[lang]} navigation`);
    const guides = language.tabs[0];
    guides.groups = guides.groups.filter((group) => !isRecipeGroup(group));
    const after = guides.groups.findIndex((group) => group.pages?.some((page) => typeof page === "string" && page.endsWith("/usage/pipelines/readme")));
    guides.groups.splice(after >= 0 ? after + 1 : guides.groups.length, 0, navGroup(lang));
  }
  return next;
}

async function listGenerated() {
  const found = [];
  for (const lang of LANGS) {
    const dir = path.join(ROOT, lang, "recipes");
    const walk = async (d) => {
      let entries = [];
      try { entries = await readdir(d, { withFileTypes: true }); } catch { return; }
      for (const e of entries) {
        const full = path.join(d, e.name);
        if (e.isDirectory()) await walk(full);
        else found.push(path.relative(ROOT, full));
      }
    };
    await walk(dir);
  }
  return found;
}

async function main() {
  const files = expectedFiles();
  const docsPath = path.join(ROOT, "docs.json");
  const docsRaw = await readFile(docsPath, "utf8");
  const docsNext = `${JSON.stringify(withNavigation(JSON.parse(docsRaw)), null, 2)}\n`;
  const drift = [];

  for (const [rel, content] of files) {
    let current = null;
    try { current = await readFile(path.join(ROOT, rel), "utf8"); } catch { /* missing */ }
    if (current !== content) {
      drift.push(rel);
      if (!CHECK) {
        await mkdir(path.dirname(path.join(ROOT, rel)), { recursive: true });
        await writeFile(path.join(ROOT, rel), content);
      }
    }
  }
  for (const rel of await listGenerated()) {
    if (!files.has(rel)) {
      drift.push(rel);
      if (!CHECK) await rm(path.join(ROOT, rel));
    }
  }
  if (JSON.stringify(JSON.parse(docsRaw)) !== JSON.stringify(JSON.parse(docsNext))) {
    drift.push("docs.json");
    if (!CHECK) await writeFile(docsPath, docsNext);
  }

  if (CHECK && drift.length) {
    console.error(`Recipe pages are out of date (${drift.length} files). Run: npm run generate:recipes`);
    process.exit(1);
  }
  console.log(`${CHECK ? "Checked" : "Generated"} ${files.size} recipe pages${drift.length && !CHECK ? `, updated ${drift.length} files` : ""}`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});

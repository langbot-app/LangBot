import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const repoRoot = new URL("../", import.meta.url);
const cjk = /[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/u;

test("repository-only English README is excluded from Mintlify publishing", async () => {
  const mintignore = await readFile(new URL(".mintignore", repoRoot), "utf8");
  const patterns = mintignore
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));

  let ignored = false;
  for (const pattern of patterns) {
    if (pattern === "README_EN.md") ignored = true;
    if (pattern === "!README_EN.md") ignored = false;
  }

  assert.equal(ignored, true);
});

test("the historical README_EN URL keeps its permanent canonical redirect", async () => {
  const docs = JSON.parse(await readFile(new URL("docs.json", repoRoot), "utf8"));
  const redirects = docs.redirects.filter(
    (item) => item.source === "/README_EN",
  );

  assert.equal(redirects.length, 1);
  assert.equal(redirects[0].destination, "/en/insight/guide");
  assert.notEqual(redirects[0].permanent, false);
});

test("navbar is localized and links to locale-aware product pages", async () => {
  const docs = JSON.parse(await readFile(new URL("docs.json", repoRoot), "utf8"));
  const languages = Object.fromEntries(
    docs.navigation.languages.map((item) => [item.language, item.navbar]),
  );
  const expected = {
    en: {
      labels: ["Cloud", "Extensions", "Blog", "Roadmap"],
      roadmap: "https://langbot.app/en/roadmap",
    },
    cn: {
      labels: ["云服务", "扩展", "博客", "路线图"],
      roadmap: "https://langbot.app/zh/roadmap",
    },
    jp: {
      labels: ["クラウド", "拡張機能", "ブログ", "ロードマップ"],
      roadmap: "https://langbot.app/ja/roadmap",
    },
  };

  for (const [language, navbar] of Object.entries(languages)) {
    assert.ok(expected[language], `unexpected language: ${language}`);
    assert.deepEqual(
      navbar.links.map((link) => link.label),
      expected[language].labels,
    );
    assert.deepEqual(
      navbar.links.map((link) => link.icon),
      ["cloud", "blocks", "newspaper", "map"],
    );
    assert.equal(navbar.links.at(-1).href, expected[language].roadmap);
    assert.equal(navbar.primary.type, "button");
    assert.equal(navbar.primary.label, "GitHub");
    assert.equal(navbar.primary.icon, "github");
    assert.equal(
      navbar.primary.href,
      "https://github.com/langbot-app/LangBot",
    );
  }

  assert.deepEqual(
    docs.navbar.links.map((link) => link.label),
    expected.en.labels,
  );
  assert.deepEqual(
    docs.navbar.links.map((link) => link.icon),
    ["cloud", "blocks", "newspaper", "map"],
  );
  assert.equal(docs.navbar.primary.icon, "github");
});

test("custom robots policy is served from the Mintlify project root", async () => {
  const robots = await readFile(new URL("robots.txt", repoRoot), "utf8");
  assert.match(robots, /^User-agent: \*$/m);
  assert.match(robots, /^Allow: \/_next\/$/m);
  assert.match(
    robots,
    /^Sitemap: https:\/\/langbot\.app\/docs\/sitemap\.xml$/m,
  );
  assert.match(
    robots,
    /^Sitemap: https:\/\/langbot\.app\/docs\/sitemap-alternates\.xml$/m,
  );
  assert.doesNotMatch(robots, /https:\/\/docs\.langbot\.app/);
});

test("alternate sitemap declares reciprocal en, zh-CN, ja and x-default links", async () => {
  const sitemap = await readFile(
    new URL("sitemap-alternates.xml", repoRoot),
    "utf8",
  );
  const blocks = [...sitemap.matchAll(/<url>([\s\S]*?)<\/url>/g)].map(
    (match) => match[1],
  );
  assert.ok(blocks.length > 0);
  assert.match(sitemap, /https:\/\/langbot\.app\/docs\//);
  assert.doesNotMatch(sitemap, /https:\/\/docs\.langbot\.app\//);

  const groups = new Map();
  for (const block of blocks) {
    const loc = block.match(/<loc>([^<]+)<\/loc>/)?.[1];
    assert.ok(loc);
    const links = Object.fromEntries(
      [...block.matchAll(/hreflang="([^"]+)" href="([^"]+)"/g)].map(
        (match) => [match[1], match[2]],
      ),
    );
    assert.ok(links.en);
    assert.ok(links["zh-CN"]);
    assert.equal(links["x-default"], links.en);
    const reciprocalUrls = [links.en, links["zh-CN"], links.ja].filter(Boolean);
    const key = reciprocalUrls.join("\n");
    groups.set(key, [...(groups.get(key) ?? []), loc]);
  }

  assert.ok(groups.size > 0);
  for (const [key, locations] of groups) {
    assert.deepEqual(locations.sort(), key.split("\n").sort());
  }
});

test("English Service API specification contains no CJK copy", async () => {
  const source = await readFile(
    new URL("openapi/service-api-en.json", repoRoot),
    "utf8",
  );
  assert.doesNotThrow(() => JSON.parse(source));
  const matches = [...source.matchAll(new RegExp(cjk.source, "gu"))];
  assert.equal(matches.length, 0, `found ${matches.length} CJK code points`);
});

test("translated English API routes preserve every historical Chinese URL", async () => {
  const docs = JSON.parse(await readFile(new URL("docs.json", repoRoot), "utf8"));
  const redirects = docs.redirects.filter((item) =>
    item.source.startsWith("/en/api-reference/") && cjk.test(item.source),
  );
  cjk.lastIndex = 0;

  assert.equal(redirects.length, 57);
  assert.equal(new Set(redirects.map((item) => item.source)).size, 57);
  for (const redirect of redirects) {
    assert.equal(redirect.permanent, true);
    assert.match(redirect.destination, /^\/en\/api-reference\//);
    assert.doesNotMatch(redirect.destination, cjk);
    cjk.lastIndex = 0;
  }
});

test("every Markdown image in the English guide has descriptive alt text", async () => {
  const guide = await readFile(
    new URL("en/insight/guide.mdx", repoRoot),
    "utf8",
  );
  const images = [...guide.matchAll(/!\[([^\]]*)\]\(([^)]+)\)/g)];
  assert.ok(images.length > 0, "expected at least one Markdown image");

  for (const [, alt, src] of images) {
    assert.ok(alt.trim().length >= 8, `${src} is missing descriptive alt text`);
  }
});

test("localized config examples use locale-appropriate YAML comments", async () => {
  const locales = {
    en: { required: /[A-Za-z]/u, forbidden: cjk },
    zh: { required: /[\u3400-\u4DBF\u4E00-\u9FFF]/u },
    ja: { required: /[\u3040-\u30FF]/u },
  };

  for (const [locale, rules] of Object.entries(locales)) {
    const page = await readFile(
      new URL(`${locale}/deploy/settings.mdx`, repoRoot),
      "utf8",
    );
    const yaml = page.match(/```yaml\n([\s\S]*?)\n```/)?.[1];
    assert.ok(yaml, `${locale} settings page has no YAML block`);

    const comments = yaml
      .split(/\r?\n/)
      .filter((line) => line.includes("#"))
      .map((line) => line.slice(line.indexOf("#") + 1).trim());
    assert.ok(comments.length >= 50, `${locale} config needs explanatory comments`);

    for (const comment of comments) {
      assert.match(comment, rules.required, `${locale}: ${comment}`);
      if (rules.forbidden) {
        assert.doesNotMatch(comment, rules.forbidden, `${locale}: ${comment}`);
      }
    }
  }
});


test("guide preserves the introduction and adds ordered navigation plus a copyable AI prompt", async () => {
  const sections = {
    zh: ["能用它做什么", "从这里开始", "让 AI Agent 帮你部署和使用"],
    en: ["What You Can Build", "Start Here", "Let an AI agent help you deploy and use LangBot"],
    ja: ["何ができるか", "はじめに", "AI エージェントに導入・利用を手伝ってもらう"],
  };
  for (const [locale, [useCases, start, title]] of Object.entries(sections)) {
    const guide = await readFile(new URL(`${locale}/insight/guide.mdx`, repoRoot), "utf8");
    const overview = guide.indexOf(`## ${useCases}`);
    const navigation = guide.indexOf(`## ${start}`);
    const assistant = guide.indexOf(`<Tip title="${title}">`);
    assert.ok(overview > 0 && navigation > overview && assistant > navigation);
    assert.ok(guide.includes("/images/zh/insight/dashboard-overview.png"));
    assert.match(guide.slice(navigation, assistant), /^1\. /m);
    assert.match(guide.slice(navigation, assistant), /^5\. /m);
    assert.doesNotMatch(guide, /^### \d+\.|127\.0\.0\.1:5300|<Steps>/m);
    const prompt = guide.slice(assistant).match(/```text\n([\s\S]*?)\n```/);
    assert.ok(prompt, `${locale}: missing copyable prompt`);
    assert.ok(prompt[1].includes("https://langbot.app/llms.txt"));
    assert.ok(prompt[1].includes("CLI"));
    assert.doesNotMatch(prompt[1], /https:\/\/langbot.app\/docs\//);
    for (const page of ["insight/features", "insight/platform-features", "usage/platforms/readme", "usage/models/readme", "usage/pipelines/readme"]) {
      await readFile(new URL(`${locale}/${page}.mdx`, repoRoot), "utf8");
    }
    for (const [, href] of guide.matchAll(/(?<!!)\]\((\/[^)]+)\)/g)) {
      if (href.startsWith("/images/")) continue;
      assert.ok(href.startsWith(`/${locale}/`), `cross-locale guide link: ${href}`);
      await readFile(new URL(`${href.slice(1)}.mdx`, repoRoot), "utf8");
    }
  }
});

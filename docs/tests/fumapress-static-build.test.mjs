import assert from "node:assert/strict";
import { access, readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { collectMdxDocuments } from "../scripts/prepare-fumapress.mjs";
import { zhOnlyArticleRoutes } from "./article-routes.mjs";

const root = path.resolve(import.meta.dirname, "..");
const articleManifest = JSON.parse(await readFile(path.join(root, "scripts/blog-articles-manifest.json"), "utf8"));
// The fixed documentation baseline excludes synchronized Blog pages.
const expectedDocuments = 299 + articleManifest.articles.length;

const publicRoot = path.join(root, "dist/public");

test("the documentation keeps a neutral base with custom section and TOC treatments", async () => {
  const css = await readFile(path.join(root, "src/app.css"), "utf8");
  assert.match(css, /fumadocs-ui\/css\/neutral\.css/);
  assert.doesNotMatch(css, /fumadocs-ui\/css\/ocean\.css/);
  assert.match(css, /#nd-toc > div > div/);
  assert.match(css, /#nd-toc > div > div > a > svg/);
  assert.match(css, /#nd-toc > div > div > div\.absolute/);
  assert.match(css, /\[data-toc-popover-content\].*> div\.absolute/s);
  assert.match(css, /a\[data-active="true"\]::before/);
  assert.match(css, /\[data-toc-popover-content\] a\[href\^="#"\]\[data-active="true"\]::before/);
  assert.match(css, /inset-inline-start: 0\.5rem/);
  assert.match(css, /border-radius: 0/);
});

async function collectHtmlRoutes(directory) {
  const routes = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) routes.push(...await collectHtmlRoutes(target));
    else if (entry.name === "index.html") routes.push(target);
  }
  return routes;
}

function staticHtmlForCanonicalDocument(document) {
  const parts = document.replace(/\.mdx$/, "").split("/");
  if (parts.at(-1) === "index") parts.pop();
  return path.join(publicRoot, ...parts, "index.html");
}

function staticHtmlForUrlPath(urlPath) {
  const parts = urlPath.replace(/^\/docs(?:\/|$)/, "").replace(/^\//, "").replace(/\/$/, "").split("/")
    .map((segment) => decodeURIComponent(segment));
  return path.join(publicRoot, ...parts, "index.html");
}

test("all canonical localized documents have static HTML", async () => {
  const documents = await collectMdxDocuments(root);
  assert.equal(documents.length, expectedDocuments);
  const missing = [];
  for (const document of documents) {
    try {
      await access(staticHtmlForCanonicalDocument(document));
    } catch {
      missing.push(document);
    }
  }
  assert.deepEqual(missing, []);
});

test("every fixed redirect destination resolves to generated output", async () => {
  const redirects = (await readFile(path.join(publicRoot, "_redirects"), "utf8"))
    .trim().split("\n").map((line) => line.split(/\s+/));
  for (const [source, destination] of redirects) {
    if (destination.includes(":splat")) continue;
    await access(staticHtmlForUrlPath(destination), undefined, `${source} -> ${destination}`);
  }
});

test("static output uses decoded filesystem paths for edge hosting", async () => {
  const encodedComponents = [];
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (/%[0-9A-Fa-f]{2}/.test(entry.name)) encodedComponents.push(path.join(directory, entry.name));
      if (entry.isDirectory()) await walk(path.join(directory, entry.name));
    }
  }
  await walk(publicRoot);
  assert.deepEqual(encodedComponents, []);
});

test("static routes never repeat their locale prefix", async () => {
  for (const locale of ["en", "zh", "ja"]) {
    await assert.rejects(access(path.join(publicRoot, locale, locale)), { code: "ENOENT" });
  }
});

test("representative localized guides and canonical host are emitted", async () => {
  for (const locale of ["en", "zh", "ja"]) {
    await access(path.join(publicRoot, locale, "insight/guide/index.html"));
  }
  const sitemap = await readFile(path.join(publicRoot, "sitemap.xml"), "utf8");
  const robots = await readFile(path.join(publicRoot, "robots.txt"), "utf8");
  assert.match(sitemap, /https:\/\/langbot\.app\/docs\//);
  assert.doesNotMatch(sitemap, /https:\/\/docs\.langbot\.app\//);
  assert.match(robots, /https:\/\/langbot\.app\/docs\/sitemap\.xml/);
  assert.doesNotMatch(robots, /https:\/\/docs\.langbot\.app\//);
});

test("platform navigation renders logo assets instead of icon path text", async () => {
  for (const locale of ["en", "zh", "ja"]) {
    const html = await readFile(
      path.join(publicRoot, locale, "usage/platforms/discord/index.html"),
      "utf8",
    );
    const asideStart = html.indexOf('<aside id="nd-sidebar"');
    const asideEnd = html.indexOf("</aside>", asideStart);
    const sidebar = html.slice(asideStart, asideEnd);
    assert.match(
      sidebar,
      /<img[^>]+src="\/docs\/images\/platforms\/discord\.svg"[^>]*>/,
      `${locale} sidebar is missing the Discord logo`,
    );
    assert.match(sidebar, />Discord</, `${locale} sidebar is missing the platform title`);
    assert.doesNotMatch(
      sidebar,
      />\/images\/platforms\/discord\.svg(?:<!-- -->)?Discord</,
      `${locale} sidebar exposes the icon path as text`,
    );
  }
});

test("nested bot groups preserve the logos declared in docs.json", async () => {
  const html = await readFile(
    path.join(publicRoot, "zh/usage/platforms/discord/index.html"),
    "utf8",
  );
  const asideStart = html.indexOf('<aside id="nd-sidebar"');
  const asideEnd = html.indexOf("</aside>", asideStart);
  const sidebar = html.slice(asideStart, asideEnd);
  for (const [title, logo] of [
    ["企业微信", "wecom.svg"],
    ["微信", "wechat.svg"],
    ["QQ 官方机器人", "qq.svg"],
    ["QQ (OneBot v11)", "qq.svg"],
  ]) {
    const escapedTitle = title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const escapedLogo = logo.replace(".", "\\.");
    assert.match(
      sidebar,
      new RegExp(`<img[^>]+src="/docs/images/platforms/${escapedLogo}"[^>]*>\\s*${escapedTitle}<svg`),
      `zh sidebar is missing the ${logo} logo for ${title}`,
    );
  }
  assert.doesNotMatch(
    sidebar,
    />robot(?:<!-- -->)?Satori/,
    "zh sidebar exposes the named robot icon as text",
  );
  assert.match(
    sidebar,
    /<svg[^>]+class="[^"]*lucide-bot[^"]*"[^>]*>[\s\S]*?<\/svg>Satori/,
    "zh sidebar is missing the Satori robot icon",
  );
});

test("all locales emit the OpenAPI surface with endpoint semantics", async () => {
  const representatives = {
    en: ["system/get-system-information", "Get system information", "GET", "/api/v1/system/info"],
    zh: ["系统/获取系统信息", "获取系统信息", "GET", "/api/v1/system/info"],
    ja: ["system/获取系统信息", "获取系统信息", "GET", "/api/v1/system/info"],
  };
  const sitemap = await readFile(path.join(publicRoot, "sitemap.xml"), "utf8");

  for (const [locale, [representativePath, ...semantics]] of Object.entries(representatives)) {
    const apiRoot = path.join(publicRoot, locale, "api-reference");
    const routes = await collectHtmlRoutes(apiRoot);
    assert.ok(routes.length >= 50, `${locale} emitted only ${routes.length} API routes`);

    const encodedRepresentativePath = representativePath.split("/").map((segment) => encodeURIComponent(segment)).join("/");
    const representative = path.join(apiRoot, representativePath, "index.html");
    const html = await readFile(representative, "utf8");
    for (const semantic of semantics) assert.ok(html.includes(semantic), `${locale} page is missing ${semantic}`);
    assert.ok(sitemap.includes(`https://langbot.app/docs/${locale}/api-reference/${encodedRepresentativePath}`));

    const spec = JSON.parse(await readFile(path.join(root, `openapi/service-api-${locale}.json`), "utf8"));
    const tagOrder = [];
    for (const pathItem of Object.values(spec.paths ?? {})) {
      for (const operation of Object.values(pathItem)) {
        if (!operation || typeof operation !== "object") continue;
        for (const tag of operation.tags ?? []) if (!tagOrder.includes(tag)) tagOrder.push(tag);
      }
    }
    const asideStart = html.indexOf('<aside id="nd-sidebar"');
    const asideEnd = html.indexOf("</aside>", asideStart);
    const sidebar = html.slice(asideStart, asideEnd);
    assert.match(sidebar, /<p[^>]*>HTTP API Reference<\/p>/, `${locale} OpenAPI section is missing`);
    let previousTag = -1;
    for (const tag of tagOrder) {
      const position = sidebar.indexOf(`>${tag}<`);
      assert.ok(position > previousTag, `${locale} OpenAPI tag order changed at ${tag}`);
      previousTag = position;
    }
  }
});

test("canonical sitemap preserves legacy routes and includes current documents", async () => {
  const legacy = new Set((await readFile(path.join(root, "tests/fixtures/legacy-sitemap-routes.txt"), "utf8"))
    .trim().split("\n").map((route) => route.replace(/\/$/, "")));
  // Mintlify accidentally indexed this repository maintenance note; preserve
  // its URL as a redirect without treating it as public documentation.
  legacy.delete("/scripts/README-blog-articles");
  // New guides added after migration extend, rather than replace, the legacy routes.
  for (const locale of ["en", "zh", "ja"]) {
    legacy.add(`/${locale}/usage/platforms/mattermost`);
    legacy.add(`/${locale}/plugin/certified-plugins`);
  }
  for (const route of zhOnlyArticleRoutes) legacy.add(`/zh/${route}`);
  const sitemap = await readFile(path.join(publicRoot, "sitemap.xml"), "utf8");
  const actual = new Set([...sitemap.matchAll(/<loc>https:\/\/langbot\.app\/docs(\/[^<]+)<\/loc>/g)]
    .map((match) => decodeURIComponent(match[1]).replace(/\/$/, "")));
  const expected = new Set(legacy);
  for (const document of await collectMdxDocuments(root)) {
    expected.add(`/${document.replace(/\.mdx$/, "").replace(/\/index$/, "")}`);
  }
  assert.deepEqual([...actual].sort(), [...expected].sort());
});

const locales = ["en", "zh", "ja"];
const hreflangByLocale = { en: "en", zh: "zh-CN", ja: "ja" };
const zhOnlyRoutes = [
  ...zhOnlyArticleRoutes,
  "develop/adapter/discord/README",
  "develop/adapter/discord/api_reference",
  "develop/adapter/discord/design",
  "develop/adapter/discord/quick_start",
  "develop/adapter/discord/troubleshooting",
  "tob/contact",
  "tob/index",
  "tob/platform",
  "tob/provider",
  "usage/pipelines/tbox",
  "usage/platforms/qq/official",
  "usage/platforms/wechat/wechatpad",
  "workshop/shengsuanyun-integration",
  "workshop/tokenpony-integration",
];

function routeFromHtml(file) {
  const relative = path.relative(publicRoot, path.dirname(file)).split(path.sep).join("/");
  return `/${relative}`.replace(/\/$/, "");
}

function extractHeadLinks(html, rel) {
  return [...html.matchAll(/<link\s+([^>]+)>/g)]
    .map((match) => match[1])
    .filter((attributes) => new RegExp(`(?:^|\\s)rel="${rel}"(?:\\s|$)`).test(attributes))
    .map((attributes) => ({
      href: attributes.match(/(?:^|\s)href="([^"]+)"/)?.[1]?.replaceAll("&amp;", "&"),
      hreflang: attributes.match(/(?:^|\s)hrefLang="([^"]+)"/i)?.[1],
    }));
}

test("rendered navbar and documentation tree use each locale's docs.json labels", async () => {
  const expected = {
    en: ["Roadmap", "https://langbot.app/en/roadmap", "Guides", "Quick Start", "Installation", "Developers", "Articles", "API Reference"],
    zh: ["路线图", "https://langbot.app/zh/roadmap", "指南", "快速开始", "安装部署", "开发者", "文章", "API 参考"],
    ja: ["ロードマップ", "https://langbot.app/ja/roadmap", "ガイド", "クイックスタート", "インストール", "開発者", "記事", "API リファレンス"],
  };
  const removedHomeLinks = {
    en: "https://langbot.app/en",
    zh: "https://langbot.app/zh",
    ja: "https://langbot.app/ja",
  };
  for (const locale of locales) {
    const html = await readFile(path.join(publicRoot, locale, "insight/guide/index.html"), "utf8");
    for (const value of expected[locale]) assert.ok(html.includes(value), `${locale} navbar missing ${value}`);
    assert.match(html, /<img[^>]+src="\/docs\/langbot-logo\.png"[^>]*>/, `${locale} docs brand logo is not base-path scoped`);
    assert.doesNotMatch(html, /<img[^>]+src="\/langbot-logo\.png"[^>]*>/, `${locale} docs brand logo points outside /docs`);
    assert.ok(!html.includes(`href="${removedHomeLinks[locale]}"`), `${locale} navbar still includes Home`);
    for (const languageName of ["English", "简体中文", "日本語"]) {
      assert.ok(html.includes(languageName), `${locale} language selector missing ${languageName}`);
    }
    for (const other of locales.filter((item) => item !== locale)) {
      assert.ok(!html.includes(expected[other][1]), `${locale} navbar includes ${other} roadmap link`);
    }
  }
});

function collectNavigationPages(value, output = []) {
  if (typeof value === "string") output.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectNavigationPages(item, output));
  else if (value && typeof value === "object") {
    if (value.hidden) return output;
    for (const key of ["tabs", "groups", "pages"]) {
      if (Array.isArray(value[key])) collectNavigationPages(value[key], output);
    }
  }
  return output;
}

function firstNavigationPage(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const page = firstNavigationPage(item);
      if (page) return page;
    }
  } else if (value && typeof value === "object" && !value.hidden) {
    return firstNavigationPage(value.pages ?? value.groups ?? []);
  }
}

function escapeHtml(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

test("docs.json tabs and groups render as root selectors and non-collapsible sections", async () => {
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const localeMap = { en: "en", cn: "zh", jp: "ja" };
  for (const language of docs.navigation.languages) {
    const locale = localeMap[language.language];
    for (const tab of language.tabs.filter((item) => !item.hidden)) {
      const sourcePage = firstNavigationPage(tab.groups);
      assert.ok(sourcePage, `${locale} ${tab.tab} has no representative page`);
      const route = sourcePage.replace(/\/index$/, "");
      const html = await readFile(path.join(publicRoot, route, "index.html"), "utf8");
      const asideStart = html.indexOf('<aside id="nd-sidebar"');
      const asideEnd = html.indexOf("</aside>", asideStart);
      const sidebar = html.slice(asideStart, asideEnd);
      assert.ok(sidebar.includes(`>${escapeHtml(tab.tab)}</p>`), `${locale} ${tab.tab} is not the root selector`);
      for (const group of tab.groups.filter((item) => !item.hidden)) {
        assert.ok(sidebar.includes(`>${escapeHtml(group.group)}</p>`), `${locale} ${tab.tab}/${group.group} is not a section label`);
      }
    }
  }
});

test("every legacy navigation entry resolves to its exact sidebar URL", async () => {
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const localeMap = { en: "en", cn: "zh", jp: "ja" };
  const failures = [];
  for (const language of docs.navigation.languages) {
    const locale = localeMap[language.language];
    const pages = collectNavigationPages(language.tabs ?? []);
    for (const page of pages) {
      if (!page.startsWith(`${locale}/`)) continue;
      const route = page.replace(/\/index$/, "");
      const htmlPath = path.join(publicRoot, route, "index.html");
      const html = await readFile(htmlPath, "utf8");
      const asideStart = html.indexOf('<aside id="nd-sidebar"');
      const asideEnd = html.indexOf("</aside>", asideStart);
      const sidebar = html.slice(asideStart, asideEnd);
      if (!sidebar.includes(`href="/docs/${route}"`)) failures.push({ page, htmlPath });
    }
  }
  assert.deepEqual(failures, []);
});

test("the Chinese quick-start navigation keeps the incumbent troubleshooting page", async () => {
  const html = await readFile(path.join(publicRoot, "zh/insight/guide/index.html"), "utf8");
  const asideStart = html.indexOf('<aside id="nd-sidebar"');
  const asideEnd = html.indexOf("</aside>", asideStart);
  const sidebar = html.slice(asideStart, asideEnd);
  assert.match(sidebar, /href="\/docs\/zh\/insight\/troubleshooting"/);
  assert.doesNotMatch(sidebar, /href="\/docs\/zh\/develop\/adapter\/discord\/troubleshooting"/);
});

test("the exact 17 zh-only sources publish no fallback en or ja routes", async () => {
  const documents = await collectMdxDocuments(root);
  const byLocale = Object.fromEntries(locales.map((locale) => [
    locale,
    new Set(documents.filter((item) => item.startsWith(`${locale}/`)).map((item) => item.slice(3).replace(/\.mdx$/, ""))),
  ]));
  const actual = [...byLocale.zh].filter((route) => !byLocale.en.has(route) && !byLocale.ja.has(route)).sort();
  assert.deepEqual(actual, zhOnlyRoutes);

  const searchableOutputs = await Promise.all(
    ["sitemap.xml", "llms.txt", "llms-full.txt", "api/search"].map((file) => readFile(path.join(publicRoot, file), "utf8")),
  );
  for (const sourceRoute of zhOnlyRoutes) {
    const route = sourceRoute === "index" ? "" : sourceRoute.replace(/\/index$/, "");
    await access(path.join(publicRoot, "zh", route, "index.html"));
    for (const locale of ["en", "ja"]) {
      await assert.rejects(access(path.join(publicRoot, locale, route, "index.html")), { code: "ENOENT" });
      for (const output of searchableOutputs) {
        assert.doesNotMatch(
          output,
          new RegExp(`/${locale}/${route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![A-Za-z0-9_-])`),
          `${locale}/${route} leaked into an index`,
        );
      }
    }
  }
});

test("every page emits a canonical and reciprocal available hreflangs", async () => {
  const sitemap = await readFile(path.join(publicRoot, "sitemap.xml"), "utf8");
  const routes = new Set([...sitemap.matchAll(/<loc>https:\/\/langbot\.app\/docs(\/[^<]+)<\/loc>/g)].map((match) => match[1].replace(/\/$/, "")));
  const allFiles = await collectHtmlRoutes(publicRoot);
  const localized = allFiles.filter((file) => routes.has(routeFromHtml(file)));
  for (const file of localized) {
    const route = routeFromHtml(file);
    const html = await readFile(file, "utf8");
    const canonical = extractHeadLinks(html, "canonical");
    assert.deepEqual(canonical, [{ href: `https://langbot.app/docs${route}`, hreflang: undefined }], route);

    const [, locale, ...suffixParts] = route.split("/");
    const suffix = suffixParts.join("/");
    const actual = Object.fromEntries(
      extractHeadLinks(html, "alternate")
        .filter((item) => item.hreflang)
        .map((item) => [item.hreflang, item.href]),
    );
    if (suffix.startsWith("api-reference/")) {
      assert.deepEqual(Object.keys(actual).sort(), ["en", "ja", "x-default", "zh-CN"]);
      assert.equal(actual["x-default"], actual.en);
      for (const href of Object.values(actual)) {
        const target = new URL(href).pathname.replace(/^\/docs/, "").replace(/\/$/, "");
        assert.ok(routes.has(target), `${route} links to missing alternate ${target}`);
      }
    } else {
      const expected = {};
      for (const candidate of locales) {
        const candidateRoute = `/${candidate}/${suffix}`.replace(/\/$/, "");
        if (routes.has(candidateRoute)) expected[hreflangByLocale[candidate]] = `https://langbot.app/docs${candidateRoute}`;
      }
      expected["x-default"] = expected.en ?? expected["zh-CN"] ?? expected.ja;
      assert.deepEqual(actual, expected, route);
    }
  }
});

test("alternate sitemap is complete, reciprocal, and advertised", async () => {
  const sitemap = await readFile(path.join(publicRoot, "sitemap-alternates.xml"), "utf8");
  const robots = await readFile(path.join(publicRoot, "robots.txt"), "utf8");
  assert.match(robots, /^Sitemap: https:\/\/langbot\.app\/docs\/sitemap\.xml$/m);
  assert.match(robots, /^Sitemap: https:\/\/langbot\.app\/docs\/sitemap-alternates\.xml$/m);

  const blocks = [...sitemap.matchAll(/<url>([\s\S]*?)<\/url>/g)].map((match) => match[1]);
  const groups = new Map();
  for (const block of blocks) {
    const loc = block.match(/<loc>([^<]+)<\/loc>/)?.[1];
    const links = Object.fromEntries([...block.matchAll(/hreflang="([^"]+)" href="([^"]+)"/g)].map((match) => [match[1], match[2]]));
    assert.ok(loc && links.en && links["zh-CN"] && links.ja && links["x-default"]);
    const key = [links.en, links["zh-CN"], links.ja].join("\n");
    groups.set(key, [...(groups.get(key) ?? []), loc]);
  }
  assert.ok(groups.size >= 155, `only ${groups.size} shared groups`);
  for (const [key, locations] of groups) assert.deepEqual(locations.sort(), key.split("\n").sort());
  for (const slug of [
    "articles",
    "articles/langbot-cloud-multi-user-workspaces",
    "articles/langbot-v4100-sandbox-skills",
    "articles/langbot-v490-rag-plugin-architecture",
    "articles/langbot-plugin-system-deep-dive",
    "articles/langtars-remote-pc-control-dify-n8n",
    "articles/connect-deepseek-to-wechat",
    "articles/deploy-ai-bot-in-5-minutes",
    "articles/dify-agent-discord-telegram-slack",
    "articles/langflow-drag-and-drop-ai-bot",
    "articles/n8n-multi-platform-ai-chatbot",
    "articles/dify-langbot-rag-knowledge-base",
    "articles/welcome",
  ]) assert.ok(sitemap.includes(`https://langbot.app/docs/en/${slug}`), `alternate sitemap missing ${slug}`);
});

test("generated pages contain no internal .html route links", async () => {
  const offenders = [];
  for (const file of await collectHtmlRoutes(publicRoot)) {
    const html = await readFile(file, "utf8");
    for (const match of html.matchAll(/href="([^"]+)"/g)) {
      const href = match[1].replaceAll("&amp;", "&");
      if (/^(?:https?:|mailto:|tel:|#|\/\/)/.test(href)) continue;
      const pathname = href.split(/[?#]/, 1)[0];
      if (pathname.endsWith(".html")) offenders.push([routeFromHtml(file), href]);
    }
    for (const match of html.matchAll(/href="(\/[^"?#]+\.html)(?:[?#][^"]*)?"/g)) offenders.push([routeFromHtml(file), match[1]]);
  }
  assert.deepEqual(offenders, []);
});


test("static search stays within Cloudflare Pages' 25 MiB file limit", async () => {
  const search = await stat(path.join(publicRoot, "api/search"));
  assert.ok(search.size <= 25 * 1024 * 1024, `search artifact is ${search.size} bytes`);
});


test("beta deployment instructions render in all six localized deployment pages", async () => {
  const composeUrl = "https://raw.githubusercontent.com/langbot-app/LangBot/dev/4.11.x/docker/docker-compose.yaml";
  for (const locale of ["en", "zh", "ja"]) {
    for (const page of ["docker", "package"]) {
      const html = await readFile(path.join(publicRoot, locale, "deploy/langbot", page, "index.html"), "utf8");
      const article = html.match(/<article\b[^>]*>([\s\S]*?)<\/article>/)?.[1];
      assert.ok(article, `${locale}/${page} has a rendered article`);
      const text = article.replace(/<[^>]+>/g, "");
      const commands = [...article.matchAll(/<pre\b[^>]*>([\s\S]*?)<\/pre>/g)]
        .map((match) => match[1].replace(/<[^>]+>/g, ""));
      if (page === "docker") {
        assert.ok(article.includes(`href="${composeUrl}"`));
        for (const literal of ["compose.yaml", "rockchin/langbot:beta", "langbot", "langbot_plugin_runtime", "langbot_box"]) {
          assert.ok(article.includes(`<code>${literal}</code>`), `${locale}/${page}: ${literal}`);
        }
        assert.ok(commands.includes("docker compose --profile all pull\ndocker compose --profile all up -d"));
      } else {
        assert.ok(commands.includes("uvx langbot@latest"));
        assert.ok(commands.includes("uvx --prerelease=allow --refresh langbot==4.11.0b3"));
      }
      assert.ok(text.includes("Beta"), `${locale}/${page} keeps the opt-in heading`);
    }
  }
});

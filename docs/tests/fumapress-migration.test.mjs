import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import {
  collectMdxDocuments,
  collectOpenApiSources,
  mapMintlifyLocale,
  normalizeMintlifyNavigationForFumapress,
  normalizeMdxContent,
  prepareFumapress,
  renderCloudflareRedirects,
} from "../scripts/prepare-fumapress.mjs";

const root = path.resolve(import.meta.dirname, "..");
const articleManifest = JSON.parse(await readFile(path.join(root, "scripts/blog-articles-manifest.json"), "utf8"));
// The fixed documentation baseline excludes synchronized Blog pages.
const expectedDocuments = 299 + articleManifest.articles.length;


test("Mintlify locales are mapped to public URL locales", () => {
  assert.equal(mapMintlifyLocale("en"), "en");
  assert.equal(mapMintlifyLocale("cn"), "zh");
  assert.equal(mapMintlifyLocale("jp"), "ja");
});

test("Fumapress navigation preserves docs.json hierarchy while removing storage locale prefixes", async () => {
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const original = structuredClone(docs);
  const normalized = normalizeMintlifyNavigationForFumapress(docs);
  assert.deepEqual(docs, original, "normalization must not mutate canonical docs.json");

  const localeMap = { en: "en", cn: "zh", jp: "ja" };
  for (const language of normalized.navigation.languages) {
    const locale = localeMap[language.language];
    const originalLanguage = original.navigation.languages.find((item) => item.language === language.language);
    assert.deepEqual(
      language.tabs.map((tab) => tab.tab),
      originalLanguage.tabs.map((tab) => tab.tab),
      `${locale} tab order changed`,
    );
    for (let tabIndex = 0; tabIndex < language.tabs.length; tabIndex += 1) {
      const actualTab = language.tabs[tabIndex];
      const expectedTab = originalLanguage.tabs[tabIndex];
      assert.deepEqual(actualTab.groups.map((group) => group.group), expectedTab.groups.map((group) => group.group));
      for (let groupIndex = 0; groupIndex < actualTab.groups.length; groupIndex += 1) {
        const actualPages = actualTab.groups[groupIndex].pages ?? [];
        const normalizePages = (value) => {
          if (typeof value === "string") return value.startsWith(`${locale}/`) ? value.slice(locale.length + 1) : value;
          if (Array.isArray(value)) return value.map(normalizePages);
          if (value && typeof value === "object") return Object.fromEntries(
            Object.entries(value).map(([key, child]) => [key, key === "pages" ? normalizePages(child) : child]),
          );
          return value;
        };
        const expectedPages = normalizePages(expectedTab.groups[groupIndex].pages ?? []);
        assert.deepEqual(actualPages, expectedPages, `${locale} navigation pages changed`);
      }
    }
  }
});

test("MDX compatibility normalization rewrites unsupported env fences", () => {
  const source = "```env\nTOKEN=value\n```\n\n~~~env title=\"example\"\nOTHER=value\n~~~\n";
  assert.equal(
    normalizeMdxContent(source, "en/insight/troubleshooting.mdx"),
    "```dotenv\nTOKEN=value\n```\n\n~~~dotenv title=\"example\"\nOTHER=value\n~~~\n",
  );
});

test("MDX compatibility normalization maps Mintlify callouts to Fumadocs", () => {
  const source = [
    "<Info title=\"Details\">",
    "Useful context.",
    "</Info>",
    "<Warning>Careful.</Warning>",
    "<Note>Remember this.</Note>",
    "<Tip>Try this.</Tip>",
    "```mdx",
    "<Info>Example only.</Info>",
    "```",
  ].join("\n");

  assert.equal(
    normalizeMdxContent(source, "en/example.mdx"),
    source
      .replace("<Info title=\"Details\">", "<Callout type=\"info\" title=\"Details\">")
      .replace("</Info>", "</Callout>")
      .replace("<Warning>Careful.</Warning>", "<Callout type=\"warning\">Careful.</Callout>")
      .replace("<Note>Remember this.</Note>", "<Callout type=\"info\">Remember this.</Callout>")
      .replace("<Tip>Try this.</Tip>", "<Callout type=\"idea\">Try this.</Callout>"),
  );
});

test("MDX compatibility normalization maps Mintlify accordions to details", () => {
  const source = [
    "<AccordionGroup>",
    "<Accordion title=\"Schema Changes\">",
    "Migration instructions.",
    "</Accordion>",
    "</AccordionGroup>",
    "```mdx",
    "<Accordion title=\"Example only\">content</Accordion>",
    "```",
  ].join("\n");

  assert.equal(
    normalizeMdxContent(source, "en/example.mdx"),
    [
      "",
      "<details>",
      "<summary>Schema Changes</summary>",
      "Migration instructions.",
      "</details>",
      "",
      "```mdx",
      "<Accordion title=\"Example only\">content</Accordion>",
      "```",
    ].join("\n"),
  );
});

test("MDX compatibility normalization makes local image assets root-relative", () => {
  const source = [
    "![local](../../../images/zh/example.png)",
    "![local with title](../../../images/zh/example.png \"Example\")",
    "![external](https://example.com/image.png)",
    "![anchor](#preview)",
    "![already root](/images/zh/example.png)",
    "<img src=\"../../../images/zh/inline.png\" alt=\"inline\" />",
    "<img src=\"https://example.com/inline.png\" alt=\"external\" />",
    "[local doc](../models/readme)",
    "```markdown",
    "![example](../../../images/zh/do-not-rewrite.png)",
    "```",
  ].join("\n");

  assert.equal(
    normalizeMdxContent(source, "en/usage/platforms/example.mdx"),
    source.replace(
      "![local](../../../images/zh/example.png)",
      "![local](/images/zh/example.png)",
    ).replace(
      "![local with title](../../../images/zh/example.png \"Example\")",
      "![local with title](/images/zh/example.png \"Example\")",
    ).replace(
      "<img src=\"../../../images/zh/inline.png\" alt=\"inline\" />",
      "<img src=\"/images/zh/inline.png\" alt=\"inline\" />",
    ),
  );
});

test("MDX compatibility normalization removes internal .html route suffixes", () => {
  const source = [
    "[absolute](/en/deploy/settings.html)",
    "[query](../settings.html?tab=bot#advanced)",
    '<a href="./basic-info.html#metadata">relative</a>',
    "[external](https://example.com/archive.html)",
    "```markdown",
    "[example](/en/keep-example.html)",
    "```",
  ].join("\n");

  assert.equal(
    normalizeMdxContent(source, "en/example.mdx"),
    source
      .replace("/en/deploy/settings.html", "/en/deploy/settings")
      .replace("../settings.html?tab=bot#advanced", "../settings?tab=bot#advanced")
      .replace("./basic-info.html#metadata", "./basic-info#metadata"),
  );
});

test("canonical MDX and nested OpenAPI sources are discovered", async () => {
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const pages = await collectMdxDocuments(root);
  assert.equal(pages.length, expectedDocuments);
  assert.deepEqual(Object.fromEntries([...pages.reduce((acc, page) => acc.set(page.split("/", 1)[0], (acc.get(page.split("/", 1)[0]) ?? 0) + 1), new Map()).entries()]), Object.fromEntries(Object.entries({ en: 94, zh: 111, ja: 94 }).map(([locale, count]) => [locale, count + articleManifest.articles.filter((article) => article.locale === locale).length])));
  assert.deepEqual(collectOpenApiSources(docs), [
    { locale: "en", source: "openapi/service-api-en.json", directory: "en/api-reference" },
    { locale: "zh", source: "openapi/service-api-zh.json", directory: "zh/api-reference" },
    { locale: "ja", source: "openapi/service-api-ja.json", directory: "ja/api-reference" },
  ]);
});

test("Cloudflare redirects preserve localized routes without overriding negotiated root", async () => {
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const lines = renderCloudflareRedirects(docs).trim().split("\n");
  assert.equal(lines.length, docs.redirects.length + 2);
  assert.ok(!lines.some((line) => line.startsWith("/ ")));
  assert.ok(lines.includes("/README_EN /en/insight/guide 308"));
  assert.ok(lines.includes("/zh/develop/adapter/discord /zh/develop/adapter/discord/README 308"));
  assert.ok(lines.includes("/scripts/README-blog-articles /en/articles 308"));
  assert.ok(lines.some((line) => line.startsWith("/en/deploy/platforms/* /en/usage/platforms/:splat ")));
  assert.ok(lines.includes("/en/api-reference/system/获取系统信息 /en/api-reference/system/get-system-information 308"));
  assert.ok(lines.includes("/en/api-reference/model-providers/创建供应商 /en/api-reference/model-providers/create-a-model-provider 308"));
});

test("Fumapress config wires static localized docs, OpenAPI, and Mintlify support", async () => {
  const config = await readFile(path.join(root, "press.config.tsx"), "utf8");
  assert.match(config, /mode:\s*[""]static[""]/);
  assert.match(config, /defineDocs\(\{[\s\S]*dir:\s*[""]content\/docs[""]/);
  assert.match(config, /docs:\s*\{[\s\S]*postprocess:\s*\{[\s\S]*includeProcessedMarkdown:\s*true/);
  assert.match(config, /localeMap:\s*\{\s*en:\s*[""]en[""],\s*cn:\s*[""]zh[""],\s*jp:\s*[""]ja[""]/);
  assert.match(config, /createOpenAPI\(/);
  for (const [locale, filename] of [["en", "service-api-en.json"], ["zh", "service-api-zh.json"], ["ja", "service-api-ja.json"]]) {
    assert.match(config, new RegExp(`input:[\\s\\S]*openapi/${filename}`));
    assert.match(config, new RegExp(`staticSource\\(\\{\\s*baseDir:\\s*["']${locale}/api-reference["']`));
  }
  assert.match(config, /groupBy:\s*["']tag["']/);
  assert.match(config, /legacyOpenApiSlug/);
  assert.match(config, /mintlifyPlugin\(/);
  assert.match(config, /openapiPlugin\(\{\s*server:\s*\w+OpenAPI\s*\}\)/);
  assert.match(config, /fumadocsMdx\(/);
});

test("prebuild is deterministic and preserves local assets and SEO files", async () => {
  const temp = await mkdtemp(path.join(tmpdir(), "langbot-fumapress-"));
  try {
    const first = await prepareFumapress({ root, outRoot: temp });
    const second = await prepareFumapress({ root, outRoot: temp });
    assert.deepEqual(first, second);
    assert.equal(first.documents, expectedDocuments);
    assert.equal(first.fallbackDefaults, 0);
    assert.equal(first.localeOnlyDocuments, 17);
    assert.equal(first.redirects, 103);
    assert.deepEqual(first.locales, ["en", "zh", "ja"]);
    await readFile(path.join(temp, "content/docs/insight/guide.mdx"), "utf8");
    await readFile(path.join(temp, "content/docs/insight/guide.zh.mdx"), "utf8");
    await readFile(path.join(temp, "content/docs/insight/guide.ja.mdx"), "utf8");
    await assert.rejects(
      readFile(path.join(temp, "content/docs/en/insight/guide.mdx"), "utf8"),
      { code: "ENOENT" },
    );
    await readFile(path.join(temp, "content/docs/develop/adapter/discord/README.zh.mdx"), "utf8");
    for (const file of ["README.mdx", "README.ja.mdx"]) {
      await assert.rejects(
        readFile(path.join(temp, "content/docs/develop/adapter/discord", file), "utf8"),
        { code: "ENOENT" },
      );
    }
    const troubleshooting = await readFile(path.join(temp, "content/docs/insight/troubleshooting.mdx"), "utf8");
    assert.match(troubleshooting, /```dotenv\nLANGBOT_BOX_ROOT=/);
    assert.doesNotMatch(troubleshooting, /```env(?:\s|$)/m);
    const dingtalk = await readFile(path.join(temp, "content/docs/usage/platforms/dingtalk.mdx"), "utf8");
    assert.match(dingtalk, /!\[DingTalk Open Platform\]\(\/images\/zh\/deploy\/bots\/dingtalk\/dingtalk1\.png\)/);
    assert.doesNotMatch(dingtalk, /\]\(\.\.\/\.\.\/\.\.\/images\//);
    await readFile(path.join(temp, "public/images/platforms/qq.svg"));
    await readFile(path.join(temp, "public/images/zh/plugin/dev/dist/github_release.png"));
    await readFile(path.join(temp, "public/openapi/service-api-en.json"));
    await readFile(path.join(temp, "public/robots.txt"), "utf8");
    await readFile(path.join(temp, "public/_redirects"), "utf8");
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { zhOnlyArticleRoutes } from "./article-routes.mjs";

const root = path.resolve(import.meta.dirname, "..");
const docs = JSON.parse(readFileSync(path.join(root, "docs.json"), "utf8"));
const manifest = JSON.parse(readFileSync(path.join(root, "scripts/blog-articles-manifest.json"), "utf8"));
const localeConfig = {
  en: { language: "en", tab: "Articles" },
  zh: { language: "cn", tab: "文章" },
  ja: { language: "jp", tab: "記事" },
};
const extraArticlePages = {
  en: [],
  zh: zhOnlyArticleRoutes.map((route) => `zh/${route}`),
  ja: [],
};

test("all canonical Blog slugs are published in every Wiki locale", () => {
  const slugsByLocale = new Map();
  for (const locale of Object.keys(localeConfig)) {
    const items = manifest.articles.filter((article) => article.locale === locale);
    assert.ok(items.length > 0, `${locale} has no articles`);
    slugsByLocale.set(locale, items.map((article) => article.slug).sort());
  }
  assert.deepEqual(slugsByLocale.get("zh"), slugsByLocale.get("en"));
  assert.deepEqual(slugsByLocale.get("ja"), slugsByLocale.get("en"));
});

test("article tabs group every generated Blog page exactly once", () => {
  for (const [locale, config] of Object.entries(localeConfig)) {
    const language = docs.navigation.languages.find((item) => item.language === config.language);
    const matchingTabs = language.tabs.filter((item) => item.tab === config.tab);
    assert.equal(matchingTabs.length, 1, `${locale} must have exactly one ${config.tab} tab`);
    const tab = matchingTabs[0];
    const pages = tab.groups.flatMap((group) => group.pages).filter((page) => page !== `${locale}/articles/index`);
    const manifestPages = manifest.articles
      .filter((article) => article.locale === locale)
      .map((article) => article.page);
    const extras = extraArticlePages[locale];
    assert.deepEqual(
      extras.filter((page) => manifestPages.includes(page)),
      [],
      `${locale} extra article pages must not overlap with the synchronized manifest`,
    );
    const expected = [...new Set(manifestPages.concat(extras))];
    assert.deepEqual([...pages].sort(), [...expected].sort());
    assert.equal(new Set(pages).size, pages.length, `${locale} has duplicate article navigation entries`);
  }
});

test("generated articles use only non-empty Wiki-local images", () => {
  const expectedImages = new Map(manifest.images.map((image) => [image.path, image]));
  for (const article of manifest.articles) {
    const file = path.join(root, `${article.page}.mdx`);
    assert.ok(existsSync(file), `missing ${article.page}.mdx`);
    const content = readFileSync(file, "utf8");
    const imageUrls = [...content.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)].map((match) => match[1]);
    for (const imageUrl of imageUrls) {
      assert.match(imageUrl, /^\/images\/articles\//, `${article.page} hotlinks ${imageUrl}`);
      const image = path.join(root, imageUrl.slice(1));
      assert.ok(existsSync(image), `${article.page} references missing ${imageUrl}`);
      assert.ok(statSync(image).size > 0, `${imageUrl} is empty`);
      const bytes = readFileSync(image);
      const expected = expectedImages.get(imageUrl);
      assert.ok(expected, `${imageUrl} is missing from the synchronization manifest`);
      assert.equal(bytes.length, expected.bytes, `${imageUrl} size differs from the manifest`);
      assert.equal(createHash("sha256").update(bytes).digest("hex"), expected.sha256, `${imageUrl} digest differs from the manifest`);
    }
  }
});

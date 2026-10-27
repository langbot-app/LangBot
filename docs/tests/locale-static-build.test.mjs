import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { browser } from "./locale-preference.test.mjs";
const root = path.resolve(import.meta.dirname, "../dist/public");

test("actual exported entry executes negotiation before body and exposes noscript links", async () => {
  const html = await readFile(path.join(root, "index.html"), "utf8");
  assert.ok(html.indexOf("<script>") < html.indexOf("<body>"));
  assert.match(html, /<noscript>/);
  for (const locale of ["en", "zh", "ja"]) assert.ok(html.includes(`href="/docs/${locale}/insight/guide"`));
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  for (const [saved, languages, expected] of [["en", ["zh-TW"], "en"], ["bad", ["ja-JP"], "ja"], [null, ["fr", "zh-TW"], "zh"], [null, ["de"], "en"]]) {
    const window = browser(saved, languages); vm.runInNewContext(script, {window});
    assert.equal(window.location.destination, `/docs/${expected}/insight/guide${window.location.search}${window.location.hash}`);
  }
  const window = browser(); Object.defineProperty(window, "localStorage", {get() {throw Error("blocked");}});
  vm.runInNewContext(script, {window}); assert.match(window.location.destination, /^\/docs\/ja\//);
  const redirects = await readFile(path.join(root, "_redirects"), "utf8");
  assert.doesNotMatch(redirects, /^\/docs\/?\s/m);
});

test("every localized HTML payload includes the preference client provider", async () => {
  let count = 0;
  async function visit(dir) {
    for (const entry of await readdir(dir, {withFileTypes: true})) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) await visit(file);
      else if (entry.name === "index.html") {
        const html = await readFile(file, "utf8");
        assert.match(html, /LocalePreferenceProvider|locale-preference-provider/, file); count++;
      }
    }
  }
  for (const locale of ["en", "zh", "ja"]) await visit(path.join(root, locale));
  // Every sitemap page plus one framework 404 page per locale.
  const sitemap = await readFile(path.join(root, "sitemap.xml"), "utf8");
  assert.equal(count, [...sitemap.matchAll(/<loc>/g)].length + 3);
});

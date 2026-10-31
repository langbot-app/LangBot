import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { unified } from "unified";
import remarkParse from "remark-parse";
import { zhOnlyArticleRoutes } from "./article-routes.mjs";

const root = path.resolve(import.meta.dirname, "..");
const output = process.env.AGENT_TEST_OUTPUT ?? path.join(root, "dist/public");
const base = "https://langbot.app/docs";
const locales = ["en", "zh", "ja"];
const read = (file) => readFile(path.join(output, file), "utf8");
const slug = (value) => value.replace(/\s+/g, "-").toLowerCase();
const encode = (value) => value.split("/").map(encodeURIComponent).join("/");
const sitemap = await read("sitemap.xml");
const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].replace(/\/$/, ""));
const relative = (url) => decodeURIComponent(url.slice(base.length + 1));
function links(node, result = []) {
  if (["link", "image", "definition"].includes(node.type)) result.push(node.url);
  for (const child of node.children ?? []) links(child, result);
  return result;
}

test("every sitemap page has meaningful canonical Markdown and HTML discovery", async () => {
  const manifest = JSON.parse(await readFile(path.join(root, "scripts/blog-articles-manifest.json"), "utf8"));
  assert.equal(urls.length, 473 + zhOnlyArticleRoutes.length + manifest.articles.length);
  for (const url of urls) {
    const route = relative(url);
    const text = await read(`${route}.md`);
    assert.ok(text.length > 100, `${route}: empty Markdown`);
    assert.ok(text.includes(url), `${route}: missing canonical URL`);
    assert.doesNotMatch(text, /__img\d+/, route);
    const html = await read(`${route}/index.html`);
    assert.ok(html.includes(`rel="alternate" type="text/markdown" href="${url}.md"`), `${route}: no Markdown discovery`);
  }
});

test("all index and full-text exports cover exactly the published pages", async () => {
  for (const locale of [null, ...locales]) {
    const prefix = locale ? `${locale}/` : "";
    const index = await read(`${prefix}llms.txt`);
    const full = await read(`${prefix}llms-full.txt`);
    assert.equal(await read(`${prefix}llm.txt`), index);
    const expected = urls.filter((url) => !locale || url.startsWith(`${base}/${locale}/`));
    const actual = links(unified().use(remarkParse).parse(index)).filter((url) => url.endsWith(".md"));
    assert.deepEqual(actual.sort(), expected.map((url) => `${url}.md`).sort());
    for (const url of expected) assert.ok(full.includes((await read(`${relative(url)}.md`)).trim()), `${prefix}full export missing ${url}`);
    for (const lang of locale ? [locale] : locales) assert.ok(index.includes(`${base}/openapi/service-api-${lang}.json`));
    assert.doesNotMatch(index, /https:\/\/docs\.langbot\.app/);
    assert.ok((await stat(path.join(output, `${prefix}llms-full.txt`))).size < 25 * 1024 * 1024);
  }
});

test("every API operation preserves the exact OpenAPI contract and auth override", async () => {
  let count = 0;
  for (const locale of locales) {
    const source = JSON.parse(await readFile(path.join(root, `openapi/service-api-${locale}.json`), "utf8"));
    assert.deepEqual(JSON.parse(await read(`openapi/service-api-${locale}.json`)), source);
    for (const [apiPath, pathItem] of Object.entries(source.paths)) {
      for (const [method, operation] of Object.entries(pathItem)) {
        if (!/^(get|put|post|delete|patch|options|head|trace)$/.test(method)) continue;
        count++;
        const route = `${locale}/api-reference/${slug(operation.tags?.[0] ?? "unknown")}/${slug(operation.summary)}`;
        const text = await read(`${route}.md`);
        assert.ok(text.includes(`${method.toUpperCase()} ${apiPath}`), route);
        assert.ok(text.includes(`${base}/${encode(route)}`), route);
        assert.ok(text.includes(`${base}/openapi/service-api-${locale}.json`), route);
        const bundle = JSON.parse(text.match(/```json\n([\s\S]*?)\n```/)?.[1] ?? "null");
        assert.ok(bundle, `${route}: missing operation bundle`);
        assert.deepEqual(bundle.paths[apiPath][method], operation, route);
        assert.deepEqual(bundle.security, operation.security ?? source.security ?? [], route);
        assert.deepEqual(bundle.servers, operation.servers ?? pathItem.servers ?? source.servers ?? [], route);
        if (bundle.security.length === 0) assert.match(text, /No authentication required/);
        else for (const alternative of bundle.security) for (const scheme of Object.keys(alternative)) {
          assert.deepEqual(bundle.components.securitySchemes[scheme], source.components.securitySchemes[scheme]);
        }
        function checkRefs(value) {
          if (!value || typeof value !== "object") return;
          if (value.$ref?.startsWith("#/")) {
            const keys = value.$ref.slice(2).split("/").map((key) => key.replaceAll("~1", "/").replaceAll("~0", "~"));
            const resolve = (document) => keys.reduce((node, key) => node?.[key], document);
            assert.ok(resolve(bundle), `${route}: unresolved ${value.$ref}`);
            assert.deepEqual(resolve(bundle), resolve(source));
          }
          for (const child of Object.values(value)) checkRefs(child);
        }
        checkRefs(bundle);
      }
    }
  }
  assert.equal(count, 177);
});

test("Markdown links and images resolve inside the embedded output", async () => {
  const failures = [];
  for (const url of urls) {
    const text = await read(`${relative(url)}.md`);
    for (const link of links(unified().use(remarkParse).parse(text))) {
      if (!link.startsWith(base) && !/^\/(?:en|zh|ja|images|docs)\//.test(link)) continue;
      if (!link.startsWith(base)) { failures.push([url, link, "unscoped URL"]); continue; }
      const target = new URL(link);
      const file = decodeURIComponent(target.pathname.replace(/^\/docs\//, ""));
      try { await stat(path.join(output, file.includes(".") ? file : `${file}/index.html`)); }
      catch { failures.push([url, link, "missing target"]); }
    }
  }
  assert.deepEqual(failures, []);
});

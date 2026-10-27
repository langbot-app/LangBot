import assert from "node:assert/strict";
import test from "node:test";
import { canonicalLink, renderMdx, operationBundle, BASE } from "../scripts/generate-agent-docs.mjs";
import { unified } from "unified";
import remarkParse from "remark-parse";

const routes = new Set(["zh/insight/guide", "zh/usage/models/readme"]);
const document = "zh/insight/guide.mdx";
test("canonical links preserve external/example URLs without trying to repair them", () => {
  for (const url of ["http://127.0.0.1:5300。", "mailto:user@example.org", "https://space.langbot.app/cloud", "https://langbot.app/zh/roadmap"]) {
    assert.equal(canonicalLink(url, document, routes), url);
  }
});
test("canonical links handle base paths, Unicode, legacy hosts, relative routes and images", () => {
  for (const url of ["/zh/usage/models/readme", "/docs/zh/usage/models/readme", "../usage/models/readme.html", "https://docs.langbot.app/zh/usage/models/readme.html", `${BASE}/zh/usage/models/readme.md`]) {
    assert.equal(canonicalLink(`${url}?q=1#model`, document, routes), `${BASE}/zh/usage/models/readme.md?q=1#model`);
  }
  assert.equal(canonicalLink("../../images/测试.png", document, routes), `${BASE}/images/%E6%B5%8B%E8%AF%95.png`);
  assert.equal(canonicalLink("#local", document, routes), "#local");
});
test("MDX exports preserve prose, wrapper content, literal images and code samples", () => {
  const source = '---\ntitle: "Test"\ndescription: "Description"\n---\n\n<Warning>\nDanger **now**.\n</Warning>\n\n<Accordion title="More">\nMore text.\n</Accordion>\n\n<img src="/images/example.png" alt="Example" />\n\n[Models](/zh/usage/models/readme.html)\n\n```python\nprint("/images/foo", "/zh/usage/models/readme.html", "<Info>")\n```\n';
  const result = renderMdx(source, document, routes).markdown;
  assert.match(result, /Danger \*\*now\*\*/);
  assert.match(result, /\*\*More\*\*/);
  assert.match(result, /More text/);
  assert.ok(result.includes(`![Example](${BASE}/images/example.png)`));
  assert.ok(result.includes(`[Models](${BASE}/zh/usage/models/readme.md)`));
  const tree = unified().use(remarkParse).parse(result);
  assert.equal(tree.children.find((node) => node.type === "code").value, 'print("/images/foo", "/zh/usage/models/readme.html", "<Info>")');
  assert.doesNotMatch(result, /<\/?(?:Warning|Accordion)|__img/);
});
test("semantic JSX preserves titles and card links; unknown components fail closed", () => {
  const source = '---\ntitle: Test\n---\n<Callout title="Important" type="warning">\nRead this.\n</Callout>\n\n<Card title="Models" href="/zh/usage/models/readme">\nConfigure models.\n</Card>\n\n<Step title="Install">\nRun setup.\n</Step>\n\n<Tab title="Linux">\nUse shell.\n</Tab>\n';
  const result = renderMdx(source, document, routes).markdown;
  for (const title of ["Important", "Install", "Linux"]) assert.ok(result.includes(title));
  assert.ok(result.includes(`[Models](${BASE}/zh/usage/models/readme.md)`));
  assert.throws(() => renderMdx('---\ntitle: Test\n---\n<Unknown title="Lost" />', document, routes), /unsupported JSX/);
});
test("fixed redirect chains resolve with cycle detection", () => {
  const redirects = [{ source: "/old", destination: "/older" }, { source: "/older", destination: "/zh/usage/models/readme" }];
  assert.equal(canonicalLink("/old#section", document, routes, redirects), `${BASE}/zh/usage/models/readme.md#section`);
  assert.throws(() => canonicalLink("/old", document, routes, [...redirects.slice(0, 1), { source: "/older", destination: "/old" }]), /Redirect cycle/);
});
test("legacy wildcard redirects resolve through multiple rules", () => {
  const redirects = [{ source: "/deploy/:slug*", destination: "/zh/deploy/:slug*" }, { source: "/zh/deploy/:slug*", destination: "/zh/usage/:slug*" }];
  assert.equal(canonicalLink("/deploy/models/readme#model", document, routes, redirects), `${BASE}/zh/usage/models/readme.md#model`);
});
test("OpenAPI closure preserves recursive refs, path parameters and security alternatives", () => {
  const spec = { openapi: "3.0.3", info: { title: "Test", version: "1" }, security: [{ Key: [] }], components: { securitySchemes: { Key: { type: "apiKey", in: "header", name: "X-Key" } }, schemas: { Node: { type: "object", properties: { next: { $ref: "#/components/schemas/Node" } } } } }, paths: { "/items/{id}": { parameters: [{ name: "id", in: "path", required: true, schema: { type: "string" } }], get: { responses: { 200: { description: "OK", content: { "application/json": { schema: { $ref: "#/components/schemas/Node" } } } } } } } } };
  const bundle = operationBundle(spec, "/items/{id}", "get");
  assert.deepEqual(bundle.paths, spec.paths);
  assert.deepEqual(bundle.components, spec.components);
  assert.deepEqual(bundle.security, spec.security);
  const bad = structuredClone(spec);
  delete bad.components.schemas.Node;
  assert.throws(() => operationBundle(bad, "/items/{id}", "get"), /Missing OpenAPI reference/);
});

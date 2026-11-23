#!/usr/bin/env node
// Agent exports use canonical sources, not renderer-processed MDX: the latter
// replaces images with JS variables and returns no text for virtual API pages.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkMdx from "remark-mdx";
import remarkGfm from "remark-gfm";
import remarkStringify from "remark-stringify";
import { parse as parseYaml } from "yaml";
import { collectMdxDocuments, normalizeMdxContent } from "./prepare-fumapress.mjs";

const ROOT = path.resolve(import.meta.dirname, "..");
export const BASE = "https://langbot.app/docs";
export const LOCALES = ["en", "zh", "ja"];
const METHODS = /^(get|put|post|delete|patch|options|head|trace)$/;
const encode = (value) => value.split("/").map(encodeURIComponent).join("/");
const slug = (value) => value.replace(/\s+/g, "-").toLowerCase();
const pageRoute = (file) => file.replace(/\.mdx$/, "").replace(/\/index$/, "");
const text = (value) => ({ type: "text", value });
const paragraph = (children) => ({ type: "paragraph", children });
const parser = unified().use(remarkParse).use(remarkMdx).use(remarkGfm);
const printer = unified().use(remarkStringify, { fences: true, bullet: "-" }).use(remarkGfm);

export function splitFrontmatter(source) {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) throw new Error("Documentation source requires frontmatter");
  return { metadata: parseYaml(match[1]), body: source.slice(match[0].length) };
}

export function canonicalLink(value, document, routes, redirects = [], seen = new Set()) {
  if (!value || value.startsWith("#")) return value;
  let local = value;
  const absolute = /^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(value);
  if (absolute) {
    // Example URLs can contain prose punctuation; only parse our docs hosts.
    if (!/^(?:https?:)?\/\/(?:docs\.langbot\.app|langbot\.app)(?:\/|$)/i.test(value)) return value;
    const url = new URL(value, BASE);
    if (url.hostname === "docs.langbot.app") local = `${url.pathname}${url.search}${url.hash}`;
    else if (url.origin === "https://langbot.app" && (url.pathname === "/docs" || url.pathname.startsWith("/docs/"))) {
      local = `${url.pathname.slice(5) || "/"}${url.search}${url.hash}`;
    } else return value; // Marketing, API hosts, mailto and other external links.
  }
  local = local.replace(/^\/docs(?=\/|$)/, "");
  const suffixAt = local.search(/[?#]/);
  const suffix = suffixAt < 0 ? "" : local.slice(suffixAt);
  let pathname = decodeURIComponent(suffixAt < 0 ? local : local.slice(0, suffixAt));
  pathname = pathname.startsWith("/") ? pathname.slice(1) : path.posix.join(path.posix.dirname(document), pathname);
  pathname = path.posix.normalize(pathname).replace(/^\.\//, "").replace(/\/$/, "");
  if (pathname === "." || pathname === "" || LOCALES.includes(pathname)) pathname = `${LOCALES.includes(pathname) ? pathname : document.split("/")[0]}/insight/guide`;
  const candidate = pathname.replace(/\.(?:html|mdx|md)$/, "").replace(/\/index$/, "");
  if (routes.has(candidate)) return `${BASE}/${encode(candidate)}.md${suffix}`;
  // Honor the same legacy aliases as the human site, without inventing
  // locale fallbacks for documents that have no translation.
  for (const redirect of redirects) {
    const wildcard = redirect.source.match(/^(.*\/):([A-Za-z][A-Za-z0-9_]*)\*$/);
    const matches = redirect.source === `/${candidate}` || (wildcard && `/${candidate}`.startsWith(wildcard[1]));
    if (matches && redirect.destination !== redirect.source) {
      if (seen.has(candidate)) throw new Error(`Redirect cycle: ${candidate}`);
      seen.add(candidate);
      const destination = wildcard
        ? redirect.destination.replace(`:${wildcard[2]}*`, `/${candidate}`.slice(wildcard[1].length))
        : redirect.destination;
      return canonicalLink(`${destination}${suffix}`, document, routes, redirects, seen);
    }
  }
  return `${BASE}/${encode(pathname)}${suffix}`;
}

export function renderMdx(source, document, routes, redirects = []) {
  const { metadata, body } = splitFrontmatter(source);
  const tree = parser.parse(normalizeMdxContent(body, document));
  const link = (value) => canonicalLink(value, document, routes, redirects);
  function transform(node) {
    if (["mdxjsEsm", "mdxFlowExpression", "mdxTextExpression"].includes(node.type)) {
      if (/^\s*\/\*[\s\S]*\*\/\s*$/.test(node.value)) return [];
      // Never silently drop an executable source value that might contain docs.
      throw new Error(`${document}: unsupported ${node.type}: ${node.value}`);
    }
    if (node.children) node.children = node.children.flatMap(transform);
    if (["link", "image", "definition"].includes(node.type)) node.url = link(node.url);
    if (!node.type.startsWith("mdxJsx")) return [node];
    const attributes = Object.fromEntries((node.attributes ?? [])
      .filter((attribute) => attribute.type === "mdxJsxAttribute")
      .map((attribute) => [attribute.name, attribute.value]));
    const children = node.children ?? [];
    if (node.name === "img") {
      if (typeof attributes.src !== "string") throw new Error(`${document}: image requires a literal src`);
      const image = { type: "image", url: link(attributes.src), alt: attributes.alt ?? "", title: attributes.title ?? null };
      return [node.type === "mdxJsxFlowElement" ? paragraph([image]) : image];
    }
    if (node.name === "a" && typeof attributes.href === "string") {
      const anchor = { type: "link", url: link(attributes.href), children };
      return [node.type === "mdxJsxFlowElement" ? paragraph([anchor]) : anchor];
    }
    if (node.name === "br") return [node.type === "mdxJsxFlowElement" ? paragraph([text("")]) : { type: "break" }];
    if (node.name === "summary") return [paragraph([{ type: "strong", children }])];
    if (node.name === "Callout") {
      return [{ type: "blockquote", children: [paragraph([text(`${attributes.title ?? attributes.type ?? "Note"}:`)]), ...children] }];
    }
    if (["Card", "Step", "Tab"].includes(node.name)) {
      if (typeof attributes.title !== "string") throw new Error(`${document}: ${node.name} requires a literal title`);
      const title = typeof attributes.href === "string"
        ? { type: "link", url: link(attributes.href), children: [text(attributes.title)] }
        : { type: "strong", children: [text(attributes.title)] };
      return [paragraph([title]), ...children];
    }
    // Audited source wrappers; fail closed when new semantic components appear.
    if (["div", "details", "span", "Steps", "Tabs", "CardGroup"].includes(node.name)) return children;
    throw new Error(`${document}: unsupported JSX component ${node.name}`);
  }
  tree.children = tree.children.flatMap(transform);
  const title = metadata.title ?? pageRoute(document);
  const url = `${BASE}/${encode(pageRoute(document))}`;
  const description = metadata.description ? `${metadata.description}\n\n` : "";
  return { title, description: metadata.description ?? "", url, markdown: `# ${title}\n\nSource: ${url}\n\n${description}${printer.stringify(tree)}` };
}

export function operationBundle(spec, apiPath, method) {
  const item = spec.paths[apiPath];
  const operation = item[method];
  const common = Object.fromEntries(Object.entries(item).filter(([key]) => !METHODS.test(key)));
  const bundle = {
    openapi: spec.openapi,
    info: spec.info,
    servers: operation.servers ?? item.servers ?? spec.servers ?? [],
    security: operation.security ?? spec.security ?? [],
    paths: { [apiPath]: { ...common, [method]: operation } },
    components: {},
  };
  const visited = new Set();
  function include(ref) {
    if (visited.has(ref)) return;
    visited.add(ref);
    if (!ref.startsWith("#/components/")) throw new Error(`Unsupported OpenAPI reference: ${ref}`);
    const keys = ref.slice(2).split("/").map((key) => key.replaceAll("~1", "/").replaceAll("~0", "~"));
    const value = keys.reduce((node, key) => node?.[key], spec);
    if (value === undefined) throw new Error(`Missing OpenAPI reference: ${ref}`);
    let parent = bundle;
    for (const key of keys.slice(0, -1)) parent = parent[key] ??= {};
    parent[keys.at(-1)] = value;
    visit(value);
  }
  function visit(value) {
    if (!value || typeof value !== "object") return;
    if (value.$ref) include(value.$ref);
    for (const child of Object.values(value)) visit(child);
  }
  visit(bundle);
  for (const alternative of bundle.security) for (const name of Object.keys(alternative)) {
    include(`#/components/securitySchemes/${name.replaceAll("~", "~0").replaceAll("/", "~1")}`);
  }
  return bundle;
}

export function renderOperation(spec, apiPath, method, locale) {
  const operation = spec.paths[apiPath][method];
  if (!operation.summary) throw new Error(`Missing summary for ${method} ${apiPath}`);
  const route = `${locale}/api-reference/${slug(operation.tags?.[0] ?? "unknown")}/${slug(operation.summary)}`;
  const url = `${BASE}/${encode(route)}`;
  const bundle = operationBundle(spec, apiPath, method);
  const auth = bundle.security.length === 0 ? "No authentication required." :
    `Authentication (OpenAPI security alternatives; OR between entries, AND within each entry): ${JSON.stringify(bundle.security)}. See components.securitySchemes below for header names, schemes and scopes.`;
  const markdown = `# ${operation.summary}\n\nSource: ${url}\n\n## ${method.toUpperCase()} ${apiPath}\n\n${operation.description ?? ""}\n\n${auth}\n\nServers: ${bundle.servers.map((server) => server.url).join(", ") || "Relative to your LangBot instance"}. Use your own LangBot instance, not the documentation host.\n\n[Complete ${locale} OpenAPI specification](${BASE}/openapi/service-api-${locale}.json)\n\n## Operation contract\n\nThe OpenAPI subset below preserves path/operation parameters, request bodies, response codes, media types, examples and schemas. All referenced components are included transitively; resolve local JSON pointers against this document. The operation is preserved verbatim, including security overrides.\n\n\`\`\`json\n${JSON.stringify(bundle, null, 2)}\n\`\`\`\n`;
  return { route, title: operation.summary, description: `${method.toUpperCase()} ${apiPath}`, url, markdown };
}

import { deploymentGuidance } from "./deployment-guidance.mjs";

function indexText(pages, locale) {
  const languages = locale ? [locale] : LOCALES;
  const prefix = locale ? `${locale}/` : "";
  const lines = ["# LangBot Documentation", "", "> Canonical documentation for LangBot: deployment, messaging integrations, plugins, development and HTTP API reference.", "", "## Agent resources", "", `- [Complete documentation text](${BASE}/${prefix}llms-full.txt)`, `- [All-language index](${BASE}/llms.txt)`, ""];
  lines.push(deploymentGuidance(locale), "");
  for (const language of languages) {
    lines.push(`## ${language}`, "", `- [${language} documentation index](${BASE}/${language}/llms.txt)`, `- [${language} complete documentation text](${BASE}/${language}/llms-full.txt)`, `- [${language} OpenAPI specification](${BASE}/openapi/service-api-${language}.json)`, "");
    for (const page of pages.filter((page) => page.route.startsWith(`${language}/`))) {
      const label = page.title.replace(/[\[\]\\]/g, "\\$&").replace(/\s+/g, " ");
      lines.push(`- [${label}](${page.url}.md)${page.description ? `: ${page.description.replace(/\s+/g, " ")}` : ""}`);
    }
    lines.push("");
  }
  return `${lines.join("\n")}\n`;
}

export async function generateAgentDocs({ root = ROOT, output = path.join(root, "dist/public") } = {}) {
  const documents = await collectMdxDocuments(root);
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const pages = [];
  for (const locale of LOCALES) {
    const spec = JSON.parse(await readFile(path.join(root, `openapi/service-api-${locale}.json`), "utf8"));
    for (const [apiPath, item] of Object.entries(spec.paths)) for (const method of Object.keys(item).filter((key) => METHODS.test(key))) {
      pages.push(renderOperation(spec, apiPath, method, locale));
    }
  }
  const routes = new Set([...documents.map(pageRoute), ...pages.map((page) => page.route)]);
  for (const document of documents) {
    pages.push({ route: pageRoute(document), ...renderMdx(await readFile(path.join(root, document), "utf8"), document, routes, docs.redirects) });
  }
  pages.sort((a, b) => a.route.localeCompare(b.route, "en"));
  if (new Set(pages.map((page) => page.route)).size !== pages.length) throw new Error("Duplicate agent page routes");
  // Use the real static sitemap as the acceptance boundary, not a guessed count.
  const sitemap = await readFile(path.join(output, "sitemap.xml"), "utf8");
  const actual = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => decodeURIComponent(match[1].replace(/\/$/, ""))).sort();
  const expected = pages.map((page) => decodeURIComponent(page.url)).sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error("Agent sources do not match the exported sitemap");
  for (const page of pages) {
    const target = path.join(output, `${page.route}.md`);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, page.markdown);
  }
  for (const locale of [null, ...LOCALES]) {
    const prefix = locale ? `${locale}/` : "";
    const selected = pages.filter((page) => !locale || page.route.startsWith(prefix));
    const index = indexText(selected, locale);
    await writeFile(path.join(output, `${prefix}llms.txt`), index);
    await writeFile(path.join(output, `${prefix}llm.txt`), index);
    await writeFile(path.join(output, `${prefix}llms-full.txt`), `${deploymentGuidance(locale)}\n${selected.map((page) => page.markdown.trim()).join("\n\n---\n\n")}\n`);
  }
  return { pages: pages.length, documents: documents.length, operations: pages.length - documents.length };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(await generateAgentDocs());
}

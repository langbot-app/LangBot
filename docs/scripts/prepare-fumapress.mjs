#!/usr/bin/env node

import { cp, lstat, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const LOCALES = ["en", "zh", "ja"];
const MINTLIFY_LOCALE_MAP = { en: "en", cn: "zh", jp: "ja" };
const ASSET_DIRECTORIES = ["images", "logo", "ui", "openapi"];
const ROOT_ASSET_PATTERN = /\.(?:gif|html|ico|jpe?g|png|svg|txt|webp|xml)$/i;
const MINTLIFY_CALLOUT_TYPES = { Info: "info", Note: "info", Tip: "idea", Warning: "warning" };

export function mapMintlifyLocale(locale) {
  const mapped = MINTLIFY_LOCALE_MAP[locale];
  if (!mapped) throw new Error(`Unsupported Mintlify locale: ${locale}`);
  return mapped;
}

async function listFiles(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = path.posix.join(prefix, entry.name);
    const full = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Generated inputs must not contain symlinks: ${full}`);
    if (entry.isDirectory()) files.push(...await listFiles(full, relative));
    else if (entry.isFile()) files.push(relative);
  }
  return files.sort();
}

function rootRelativeAssetUrl(destination, documentPath) {
  const suffixIndex = destination.search(/[?#]/);
  const pathname = suffixIndex === -1 ? destination : destination.slice(0, suffixIndex);
  const suffix = suffixIndex === -1 ? "" : destination.slice(suffixIndex);
  const resolved = path.posix.normalize(path.posix.join(path.posix.dirname(documentPath), pathname));
  if (resolved.startsWith("../") || path.posix.isAbsolute(resolved)) return destination;
  if (!ASSET_DIRECTORIES.includes(resolved.split("/", 1)[0])) return destination;
  return `/${resolved}${suffix}`;
}

export function normalizeInternalHtmlUrl(destination) {
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(destination)) return destination;
  const suffixIndex = destination.search(/[?#]/);
  const pathname = suffixIndex === -1 ? destination : destination.slice(0, suffixIndex);
  const suffix = suffixIndex === -1 ? "" : destination.slice(suffixIndex);
  return pathname.endsWith(".html") ? `${pathname.slice(0, -5)}${suffix}` : destination;
}

export function normalizeMdxContent(content, documentPath) {
  let fence;
  return content.split(/(?<=\n)/).map((line) => {
    const body = line.replace(/\r?\n$/, "");
    if (fence) {
      if (new RegExp(`^ {0,3}${fence.character}{${fence.length},}\\s*$`).test(body)) fence = undefined;
      return line;
    }

    const opening = body.match(/^( {0,3})(`{3,}|~{3,})(.*)$/);
    if (opening) {
      fence = { character: opening[2][0], length: opening[2].length };
      const normalizedInfo = opening[3].replace(/^(\s*)env(?=\s|$)/, "$1dotenv");
      return `${opening[1]}${opening[2]}${normalizedInfo}${line.slice(body.length)}`;
    }

    return line
      .replace(/<\/?AccordionGroup>/g, "")
      .replace(/<Accordion\s+title=(["'])(.*?)\1\s*>/g, (_match, _quote, title) =>
        `<details>\n<summary>${title}</summary>`)
      .replace(/<\/Accordion>/g, "</details>")
      .replace(/<(Info|Note|Tip|Warning)(?=\s|>)([^>]*)>/g, (_match, name, attributes) =>
        `<Callout type="${MINTLIFY_CALLOUT_TYPES[name]}"${attributes}>`)
      .replace(/<\/(?:Info|Note|Tip|Warning)>/g, "</Callout>")
      .replace(/(!\[[^\]\n]*\]\(\s*)(<?)(\.\.?\/[^)\s>]+)(>?)([^)\n]*\))/g, (_match, prefix, open, destination, close, suffix) =>
        `${prefix}${open}${rootRelativeAssetUrl(destination, documentPath)}${close}${suffix}`)
      .replace(/(\]\(\s*<?)([^)\s>]+)(>?)([^)\n]*\))/g, (_match, prefix, destination, close, suffix) =>
        `${prefix}${normalizeInternalHtmlUrl(destination)}${close}${suffix}`)
      .replace(/(\bhref\s*=\s*["'])([^"']+)(["'])/g, (_match, prefix, destination, suffix) =>
        `${prefix}${normalizeInternalHtmlUrl(destination)}${suffix}`)
      .replace(/(\bsrc\s*=\s*["'])(\.\.?\/[^"']+)(["'])/g, (_match, prefix, destination, suffix) =>
        `${prefix}${rootRelativeAssetUrl(destination, documentPath)}${suffix}`);
  }).join("");
}

export async function collectMdxDocuments(root = ROOT) {
  const pages = [];
  for (const locale of LOCALES) {
    const files = await listFiles(path.join(root, locale));
    pages.push(...files.filter((file) => file.endsWith(".mdx")).map((file) => `${locale}/${file}`));
  }
  return pages.sort();
}

function visitNavigation(value, callback) {
  if (Array.isArray(value)) {
    for (const item of value) visitNavigation(item, callback);
    return;
  }
  if (!value || typeof value !== "object") return;
  callback(value);
  for (const child of Object.values(value)) visitNavigation(child, callback);
}

export function collectOpenApiSources(docs) {
  const sources = [];
  visitNavigation(docs.navigation, (item) => {
    if (!item.openapi || typeof item.openapi !== "object" || !item.openapi.source || !item.openapi.directory) return;
    const locale = item.openapi.directory.split("/", 1)[0];
    sources.push({ locale, source: item.openapi.source, directory: item.openapi.directory });
  });
  return sources.sort((left, right) => LOCALES.indexOf(left.locale) - LOCALES.indexOf(right.locale));
}

export function normalizeMintlifyNavigationForFumapress(docs) {
  const normalized = structuredClone(docs);
  for (const language of normalized.navigation?.languages ?? []) {
    const locale = mapMintlifyLocale(language.language);
    visitNavigation(language, (item) => {
      if (!Array.isArray(item.pages)) return;
      item.pages = item.pages.map((entry) =>
        typeof entry === "string" && entry.startsWith(`${locale}/`)
          ? entry.slice(locale.length + 1)
          : entry,
      );
    });
  }
  return normalized;
}

function cloudflarePattern(value, destination = false) {
  return value.replace(/:([A-Za-z][A-Za-z0-9_]*)\*/g, destination ? ":splat" : "*");
}

export function renderCloudflareRedirects(docs) {
  const lines = [
    "/zh/develop/adapter/discord /zh/develop/adapter/discord/README 308",
    "/scripts/README-blog-articles /en/articles 308",
  ];
  for (const redirect of docs.redirects ?? []) {
    const status = redirect.permanent === false ? 307 : 308;
    lines.push(`${cloudflarePattern(redirect.source)} ${cloudflarePattern(redirect.destination, true)} ${status}`);
  }
  return `${lines.join("\n")}\n`;
}

async function copyDirectory(source, destination) {
  const info = await lstat(source);
  if (!info.isDirectory() || info.isSymbolicLink()) throw new Error(`Expected a real directory: ${source}`);
  await cp(source, destination, { recursive: true, force: true, errorOnExist: false });
}

export async function prepareFumapress({ root = ROOT, outRoot = root } = {}) {
  const docs = JSON.parse(await readFile(path.join(root, "docs.json"), "utf8"));
  const documents = await collectMdxDocuments(root);
  const openapi = collectOpenApiSources(docs);
  if (openapi.length !== LOCALES.length) {
    throw new Error(`Expected one nested OpenAPI source per locale, found ${openapi.length}`);
  }
  const contentRoot = path.join(outRoot, "content");
  const publicRoot = path.join(outRoot, "public");
  await rm(contentRoot, { recursive: true, force: true });
  await rm(publicRoot, { recursive: true, force: true });
  await mkdir(path.join(contentRoot, "docs"), { recursive: true });
  await mkdir(publicRoot, { recursive: true });
  await writeFile(
    path.join(contentRoot, "fumapress-docs.json"),
    `${JSON.stringify(normalizeMintlifyNavigationForFumapress(docs), null, 2)}\n`,
  );

  const documentsByPath = new Map();
  for (const document of documents) {
    const [locale, ...relativeParts] = document.split("/");
    const relative = relativeParts.join("/");
    const translations = documentsByPath.get(relative) ?? new Map();
    translations.set(locale, document);
    documentsByPath.set(relative, translations);
  }

  let localeOnlyDocuments = 0;
  for (const [relative, translations] of [...documentsByPath].sort(([left], [right]) => left.localeCompare(right))) {
    if (!translations.has("en")) localeOnlyDocuments += 1;

    for (const [locale, document] of translations) {
      const extension = locale === "en" ? ".mdx" : `.${locale}.mdx`;
      const destination = path.join(contentRoot, "docs", relative.replace(/\.mdx$/, extension));
      await mkdir(path.dirname(destination), { recursive: true });
      const source = await readFile(path.join(root, document), "utf8");
      await writeFile(destination, normalizeMdxContent(source, document));
    }

  }
  for (const directory of ASSET_DIRECTORIES) {
    await copyDirectory(path.join(root, directory), path.join(publicRoot, directory));
  }
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (entry.isFile() && ROOT_ASSET_PATTERN.test(entry.name) && !["robots.txt", "sitemap-alternates.xml"].includes(entry.name)) {
      await cp(path.join(root, entry.name), path.join(publicRoot, entry.name), { force: true });
    }
  }

  await cp(path.join(root, "robots.txt"), path.join(publicRoot, "robots.txt"), { force: true });
  await writeFile(path.join(publicRoot, "_redirects"), renderCloudflareRedirects(docs));

  return {
    documents: documents.length,
    fallbackDefaults: 0,
    localeOnlyDocuments,
    redirects: (docs.redirects?.length ?? 0) + 2,
    locales: [...LOCALES],
    openapi,
  };
}

async function main() {
  const result = await prepareFumapress();
  console.log(`Prepared ${result.documents} MDX documents, ${result.openapi.length} OpenAPI specs, and ${result.redirects} redirects.`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

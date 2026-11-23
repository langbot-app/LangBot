#!/usr/bin/env node

import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BASE = "https://langbot.app/docs";
const LOCALES = ["en", "zh", "ja"];
const HREFLANG = { en: "en", zh: "zh-CN", ja: "ja" };

function escapeXml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function decodeXml(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&apos;", "'");
}

export function renderAlternateSitemap(sitemap, base = BASE, explicitGroups = []) {
  const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => decodeXml(match[1]));
  const groups = new Map();
  for (const url of urls) {
    for (const locale of LOCALES) {
      const prefix = `${base}/${locale}/`;
      if (!url.startsWith(prefix)) continue;
      const suffix = url.slice(prefix.length).replace(/\/$/, "");
      const group = groups.get(suffix) ?? {};
      group[locale] = url.replace(/\/$/, "");
      groups.set(suffix, group);
      break;
    }
  }

  for (const group of explicitGroups) groups.set(`explicit:${group.en}`, group);

  const shared = [...groups.values()]
    .filter((group) => LOCALES.every((locale) => group[locale]))
    .sort((left, right) => left.en.localeCompare(right.en));
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
  ];
  for (const group of shared) {
    const alternates = [
      ...LOCALES.map((locale) => [HREFLANG[locale], group[locale]]),
      ["x-default", group.en],
    ];
    for (const locale of LOCALES) {
      lines.push("  <url>", `    <loc>${escapeXml(group[locale])}</loc>`);
      for (const [language, href] of alternates) {
        lines.push(`    <xhtml:link rel="alternate" hreflang="${language}" href="${escapeXml(href)}" />`);
      }
      lines.push("  </url>");
    }
  }
  lines.push("</urlset>");
  return { xml: `${lines.join("\n")}\n`, groups: shared.length };
}

function legacyOpenApiSlug(value) {
  return value.replace(/\s+/g, "-").toLowerCase();
}

function encodeRoute(route) {
  return route.split("/").map((segment) => encodeURIComponent(segment)).join("/");
}

async function collectOpenApiAlternateGroups(root = ROOT, base = BASE) {
  const groups = new Map();
  for (const locale of LOCALES) {
    const spec = JSON.parse(await readFile(path.join(root, `openapi/service-api-${locale}.json`), "utf8"));
    for (const [apiPath, pathItem] of Object.entries(spec.paths ?? {})) {
      for (const [method, operation] of Object.entries(pathItem)) {
        if (!/^(?:get|post|put|patch|delete|head|options)$/i.test(method) || !operation?.summary) continue;
        const tag = operation.tags?.[0] ?? "unknown";
        const route = encodeRoute(`api-reference/${legacyOpenApiSlug(tag)}/${legacyOpenApiSlug(operation.summary)}`);
        const key = `${method.toLowerCase()} ${apiPath}`;
        const group = groups.get(key) ?? {};
        group[locale] = `${base}/${locale}/${route}`;
        groups.set(key, group);
      }
    }
  }
  return [...groups.values()];
}

async function loadSource(source) {
  if (/^https?:\/\//.test(source)) {
    const response = await fetch(source, { headers: { "user-agent": "LangBot docs alternate-sitemap generator" } });
    if (!response.ok) throw new Error(`Unable to fetch ${source}: ${response.status}`);
    return response.text();
  }
  return readFile(source, "utf8");
}

async function main() {
  const source = process.env.SITEMAP_SOURCE ?? path.join(ROOT, "dist/public/sitemap.xml");
  const openApiGroups = await collectOpenApiAlternateGroups();
  const { xml, groups } = renderAlternateSitemap(await loadSource(source), BASE, openApiGroups);
  const outputs = process.env.SITEMAP_OUTPUT
    ? [path.resolve(process.env.SITEMAP_OUTPUT)]
    : [path.join(ROOT, "dist/public/sitemap-alternates.xml"), path.join(ROOT, "sitemap-alternates.xml")];
  for (const output of outputs) await writeFile(output, xml);
  console.log(`Wrote ${groups} reciprocal language groups to ${outputs.join(", ")}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

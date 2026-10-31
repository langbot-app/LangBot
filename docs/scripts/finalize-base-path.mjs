#!/usr/bin/env node

import { readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PUBLIC_ROOT = path.join(ROOT, "dist/public");
const ORIGIN = "https://langbot.app";
const BASE_PATH = "/docs";
const TEXT_EXTENSIONS = new Set([".html", ".md", ".txt", ".xml", ".json", ".js", ".css"]);

async function collectTextFiles(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await collectTextFiles(target));
    else if (TEXT_EXTENSIONS.has(path.extname(entry.name)) || target.endsWith("/api/search")) files.push(target);
  }
  return files;
}

function prefixPublicAssets(content) {
  return content
    .replaceAll('"/images/', `"${BASE_PATH}/images/`)
    .replaceAll("'/images/", `'${BASE_PATH}/images/`)
    .replaceAll('"/favicon.ico"', `"${BASE_PATH}/favicon.ico"`)
    .replaceAll("'/favicon.ico'", `'${BASE_PATH}/favicon.ico'`)
    .replaceAll('"/langbot-logo.png"', `"${BASE_PATH}/langbot-logo.png"`)
    .replaceAll("'/langbot-logo.png'", `'${BASE_PATH}/langbot-logo.png'`)
    .replaceAll('"/rss.xml"', `"${BASE_PATH}/rss.xml"`)
    .replaceAll("'/rss.xml'", `'${BASE_PATH}/rss.xml'`);
}

export async function finalizeBasePath(publicRoot = PUBLIC_ROOT) {
  const sitemapPath = path.join(publicRoot, "sitemap.xml");
  const originalSitemap = await readFile(sitemapPath, "utf8");
  const sourceUrls = [...originalSitemap.matchAll(/<loc>(https:\/\/langbot\.app\/[^<]+)<\/loc>/g)]
    .map((match) => match[1].replace(/\/$/, ""));
  const replacements = sourceUrls
    .map((source) => [source, `${ORIGIN}${BASE_PATH}${source.slice(ORIGIN.length)}`])
    .sort((left, right) => right[0].length - left[0].length);

  let changed = 0;
  for (const file of await collectTextFiles(publicRoot)) {
    let content = await readFile(file, "utf8");
    const before = content;
    for (const [source, destination] of replacements) content = content.replaceAll(source, destination);
    content = content
      .replaceAll(`${ORIGIN}/sitemap.xml`, `${ORIGIN}${BASE_PATH}/sitemap.xml`)
      .replaceAll(`${ORIGIN}/sitemap-alternates.xml`, `${ORIGIN}${BASE_PATH}/sitemap-alternates.xml`);
    content = prefixPublicAssets(content);
    if (content !== before) {
      await writeFile(file, content);
      changed += 1;
    }
  }

  const redirectsPath = path.join(publicRoot, "_redirects");
  const redirects = await readFile(redirectsPath, "utf8");
  const scopedRedirects = redirects
    .split("\n")
    .map((line) => {
      if (!line.trim()) return line;
      const [source, destination, status, ...rest] = line.trim().split(/\s+/);
      const scope = (value) => value.startsWith("/") ? `${BASE_PATH}${value === "/" ? "" : value}` : value;
      return [scope(source), scope(destination), status, ...rest].filter(Boolean).join(" ");
    })
    .join("\n");
  await writeFile(redirectsPath, scopedRedirects);
  return { changed, routes: replacements.length };
}

async function main() {
  const result = await finalizeBasePath();
  console.log(`Finalized ${result.routes} documentation routes under ${BASE_PATH} across ${result.changed} files`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

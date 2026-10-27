#!/usr/bin/env node

import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { cp, lstat, mkdir, mkdtemp, readFile, readdir, realpath, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";

const ROOT = path.resolve(import.meta.dirname, "..");
const ARTICLE_LOCALES = ["en", "zh", "ja"];
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
const LANGUAGE_CONFIG = {
  en: { mintlify: "en", tab: "Articles", introTitle: "LangBot Articles", introDescription: "Product updates, engineering deep dives, tutorials, integrations, and announcements from the LangBot Blog.", sourceLabel: "This article is synchronized from the LangBot Blog.", sourceAction: "Read the canonical version", fallbackLabel: "", overviewGroup: "Browse", groups: { updates: "Product Updates", engineering: "Engineering", tutorials: "Tutorials & Integrations", announcements: "Announcements" } },
  zh: { mintlify: "cn", tab: "文章", introTitle: "LangBot 文章", introDescription: "同步自 LangBot Blog 的产品动态、技术解析、教程、集成实践与公告。", sourceLabel: "本文同步自 LangBot Blog。", sourceAction: "阅读 Blog 原文", fallbackLabel: "", overviewGroup: "浏览", groups: { updates: "产品动态", engineering: "技术解析", tutorials: "教程与集成", announcements: "公告" } },
  ja: { mintlify: "jp", tab: "記事", introTitle: "LangBot 記事", introDescription: "LangBot Blog の製品アップデート、技術解説、チュートリアル、連携事例、お知らせをまとめています。", sourceLabel: "この記事は LangBot Blog から同期されています。", sourceAction: "Blog の原文を読む", fallbackLabel: "この記事の日本語版はまだ公開されていないため、英語版を掲載しています。", overviewGroup: "一覧", groups: { updates: "製品アップデート", engineering: "エンジニアリング", tutorials: "チュートリアルと連携", announcements: "お知らせ" } },
};
const JAPANESE_TITLES = {
  "connect-deepseek-to-wechat": "DeepSeek R1 を WeChat・Discord・Telegram に5分で接続する方法",
  "deploy-ai-bot-in-5-minutes": "AI Bot を Discord・Telegram・WeChat に5分でデプロイ",
  "dify-agent-discord-telegram-slack": "Dify Agent を Discord・Telegram・Slack で動かす",
  "dify-langbot-rag-knowledge-base": "LangBot 4.6.0 外部ナレッジベース入門：Dify と連携した RAG 会話",
  "langbot-plugin-system-deep-dive": "LangBot プラグインシステム詳解：プロセス分離・イベント駆動・コンポーネント設計",
  "langbot-v4100-sandbox-skills": "LangBot v4.10.0：Agent Sandbox と Skills",
  "langbot-v490-rag-plugin-architecture": "LangBot v4.9.0：完全プラグイン化された RAG アーキテクチャ",
  "langflow-drag-and-drop-ai-bot": "Langflow のドラッグ＆ドロップでマルチプラットフォーム AI Bot を構築",
  "langtars-remote-pc-control-dify-n8n": "LangTARS：Dify・n8n と連携するオープンソース PC 操作 Agent",
  "n8n-multi-platform-ai-chatbot": "n8n と LangBot でマルチプラットフォーム AI Chatbot を構築",
  welcome: "LangBot Blog のご紹介",
};

function parseArgs(argv) {
  const result = { check: false, source: process.env.LANGBOT_LANDING_REPO || "" };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--check") result.check = true;
    else if (argv[i] === "--source") result.source = argv[++i];
    else throw new Error(`Unknown argument: ${argv[i]}`);
  }
  if (result.source) result.source = path.resolve(result.source);
  return result;
}
function parseScalar(value) {
  const trimmed = value.trim();
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) return trimmed.slice(1, -1).replaceAll('\\"', '"');
  return trimmed;
}
function parseFrontmatter(markdown, file) {
  if (!markdown.startsWith("---\n")) throw new Error(`${file}: missing frontmatter`);
  const end = markdown.indexOf("\n---\n", 4);
  if (end < 0) throw new Error(`${file}: unterminated frontmatter`);
  const raw = markdown.slice(4, end);
  const body = markdown.slice(end + 5).trimStart();
  const lines = raw.split("\n");
  const data = {};
  for (let i = 0; i < lines.length; i += 1) {
    const match = /^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$/.exec(lines[i]);
    if (!match) continue;
    const [, key, value] = match;
    if (key === "cover") {
      const cover = {};
      while (i + 1 < lines.length && /^\s+/.test(lines[i + 1])) {
        const nested = /^\s+([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$/.exec(lines[++i]);
        if (nested) cover[nested[1]] = parseScalar(nested[2]);
      }
      data.cover = cover;
    } else if (value.startsWith("[") && value.endsWith("]")) {
      data[key] = [...value.matchAll(/"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'/g)].map((item) => item[1] ?? item[2]);
    } else data[key] = parseScalar(value);
  }
  for (const required of ["title", "date", "description", "author"]) if (!data[required]) throw new Error(`${file}: missing ${required}`);
  return { data, body };
}
function yamlQuote(value) { return JSON.stringify(String(value)); }
function classify(post) {
  const category = String(post.data.categories?.[0] || "").toLowerCase();
  if (category.includes("product") || category.includes("产品") || category.includes("製品")) return "updates";
  if (category.includes("engineering") || category.includes("technical") || category.includes("技术") || category.includes("技術")) return "engineering";
  if (category.includes("announcement") || category.includes("公告") || category.includes("お知らせ")) return "announcements";
  return "tutorials";
}
function canonicalUrl(locale, slug) { return `https://langbot.app/${locale}/blog/${slug}`; }
function attribution(locale, post) {
  if (locale === "zh") return `发布于 ${post.data.date} · 作者：${post.data.author}`;
  if (locale === "ja") return `公開日：${post.data.date} · 著者：${post.data.author}`;
  return `Published ${post.data.date} · Author: ${post.data.author}`;
}
function escapeMdxProse(markdown) {
  const lines = markdown.split("\n");
  let fenced = false;
  return lines.map((line) => {
    if (/^\s*```/.test(line) || /^\s*~~~/.test(line)) { fenced = !fenced; return line; }
    if (fenced) return line.trimEnd();
    return line.split(/(`[^`]*`)/g).map((piece, index) => index % 2 === 1 ? piece : piece.replaceAll("{", "&#123;").replaceAll("}", "&#125;")).join("").trimEnd();
  }).join("\n");
}
function imageReferences(markdown) { return [...markdown.matchAll(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)/g)].map((match) => ({ alt: match[1], url: match[2], full: match[0] })); }
function contentTypeExtension(contentType) {
  if (contentType.includes("image/png")) return ".png";
  if (contentType.includes("image/jpeg")) return ".jpg";
  if (contentType.includes("image/gif")) return ".gif";
  if (contentType.includes("image/svg")) return ".svg";
  if (contentType.includes("image/webp")) return ".webp";
  return "";
}
function localImageTarget(sourceUrl) {
  if (sourceUrl.startsWith("/")) return `/images/articles/source${sourceUrl}`;
  const parsed = new URL(sourceUrl);
  let base = path.posix.basename(parsed.pathname) || "image";
  const digest = createHash("sha256").update(sourceUrl).digest("hex").slice(0, 12);
  base = base.replace(/[^A-Za-z0-9._-]/g, "-");
  return `/images/articles/external/${digest}-${base}`;
}
function assertWithin(base, candidate, label) {
  const normalizedBase = path.resolve(base);
  const normalizedCandidate = path.resolve(candidate);
  if (!normalizedCandidate.startsWith(`${normalizedBase}${path.sep}`)) throw new Error(`${label} escapes ${normalizedBase}: ${normalizedCandidate}`);
}
async function assertDirectoryWithoutSymlinks(directory, label) {
  if (!existsSync(directory)) throw new Error(`${label} does not exist: ${directory}`);
  const info = await lstat(directory);
  if (!info.isDirectory() || info.isSymbolicLink()) throw new Error(`${label} must be a real non-symlink directory: ${directory}`);
  const resolved = await realpath(directory);
  if (resolved !== path.resolve(directory)) throw new Error(`${label} path must not traverse symlinks: ${directory}`);
  return resolved;
}
async function readRegularFileWithin(base, file, label, encoding = null) {
  const baseReal = await assertDirectoryWithoutSymlinks(base, `${label} directory`);
  if (!existsSync(file)) throw new Error(`${label} does not exist: ${file}`);
  const info = await lstat(file);
  if (!info.isFile() || info.isSymbolicLink()) throw new Error(`${label} must be a regular non-symlink file: ${file}`);
  const fileReal = await realpath(file);
  assertWithin(baseReal, fileReal, label);
  return encoding ? readFile(fileReal, encoding) : readFile(fileReal);
}
function validateImageBytes(bytes, label) {
  const ascii = bytes.subarray(0, 16).toString("ascii");
  const trimmed = bytes.toString("utf8", 0, Math.min(bytes.length, 1024)).trimStart();
  const valid =
    bytes.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) ||
    (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) ||
    ascii.startsWith("GIF87a") || ascii.startsWith("GIF89a") ||
    (ascii.startsWith("RIFF") && ascii.slice(8, 12) === "WEBP") ||
    ((trimmed.startsWith("<svg") || trimmed.startsWith("<?xml")) && trimmed.includes("<svg"));
  if (!valid) throw new Error(`Invalid image signature: ${label}`);
}
async function prepareImageTarget(assetRoot, target) {
  const imageRoot = path.join(assetRoot, "images/articles");
  assertWithin(imageRoot, target, "Article image target");
  await mkdir(path.dirname(target), { recursive: true });
  const imageRootReal = await realpath(imageRoot);
  const targetParentReal = await realpath(path.dirname(target));
  if (targetParentReal !== path.resolve(path.dirname(target))) throw new Error(`Article image target directory must not be a symlink: ${path.dirname(target)}`);
  assertWithin(imageRootReal, path.join(targetParentReal, path.basename(target)), "Resolved article image target");
  if (existsSync(target) && (await lstat(target)).isSymbolicLink()) throw new Error(`Article image target must not be a symlink: ${target}`);
}
async function materializeImage(sourceRoot, sourceUrl, assetRoot) {
  let targetUrl = localImageTarget(sourceUrl);
  let target = path.join(assetRoot, targetUrl.slice(1));
  await prepareImageTarget(assetRoot, target);
  if (sourceUrl.startsWith("/")) {
    const publicRoot = path.join(sourceRoot, "public");
    const source = path.join(publicRoot, sourceUrl.slice(1));
    assertWithin(publicRoot, source, "Blog image source");
    if (!existsSync(source)) throw new Error(`Missing source image: ${sourceUrl} (${source})`);
    const sourceStat = await lstat(source);
    if (!sourceStat.isFile() || sourceStat.isSymbolicLink()) throw new Error(`Blog image source must be a regular non-symlink file: ${source}`);
    const publicRootReal = await realpath(publicRoot);
    const sourceReal = await realpath(source);
    assertWithin(publicRootReal, sourceReal, "Resolved Blog image source");
    const bytes = await readFile(sourceReal);
    validateImageBytes(bytes, sourceUrl);
    await writeFile(target, bytes);
    return targetUrl;
  }
  const parsedSource = new URL(sourceUrl);
  if (parsedSource.protocol !== "https:") throw new Error(`External images must use HTTPS: ${sourceUrl}`);
  const response = await fetch(sourceUrl, { headers: { "User-Agent": "LangBot-Wiki-Article-Sync/1.0" }, redirect: "follow" });
  if (!response.ok) throw new Error(`Failed to fetch image ${sourceUrl}: HTTP ${response.status}`);
  const declaredSize = Number(response.headers.get("content-length") || 0);
  if (declaredSize > MAX_IMAGE_BYTES) throw new Error(`Image exceeds ${MAX_IMAGE_BYTES} bytes: ${sourceUrl}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  const contentType = response.headers.get("content-type") || "";
  if (!bytes.length || bytes.length > MAX_IMAGE_BYTES || !contentType.toLowerCase().startsWith("image/")) throw new Error(`Invalid image ${sourceUrl}: ${contentType}, ${bytes.length} bytes`);
  validateImageBytes(bytes, sourceUrl);
  if (!path.extname(target)) {
    const extension = contentTypeExtension(contentType);
    if (!extension) throw new Error(`Unsupported image content type for extensionless URL: ${contentType}`);
    target += extension;
    targetUrl += extension;
    await prepareImageTarget(assetRoot, target);
  }
  if (contentType.toLowerCase().includes("image/svg")) {
    await writeFile(target, bytes.toString("utf8").replace(/[ \t]+$/gm, ""));
  } else {
    await writeFile(target, bytes);
  }
  return targetUrl;
}
async function loadPosts(sourceRoot) {
  const byLocale = new Map();
  const blogRoot = path.join(sourceRoot, "src/content/blog");
  const blogRootReal = await assertDirectoryWithoutSymlinks(blogRoot, "Blog content root");
  for (const locale of ARTICLE_LOCALES) {
    const dir = path.join(blogRoot, locale);
    const files = existsSync(dir) ? await readdir(dir) : [];
    if (existsSync(dir)) {
      const localeRootReal = await assertDirectoryWithoutSymlinks(dir, `Blog ${locale} content root`);
      assertWithin(blogRootReal, localeRootReal, `Blog ${locale} content root`);
    }
    const posts = new Map();
    for (const name of files.filter((item) => item.endsWith(".md")).sort()) {
      const file = path.join(dir, name);
      const parsed = parseFrontmatter(await readRegularFileWithin(dir, file, `Blog ${locale} article`, "utf8"), file);
      const slug = name.slice(0, -3);
      posts.set(slug, { ...parsed, slug, locale, file });
    }
    byLocale.set(locale, posts);
  }
  const enSlugs = [...byLocale.get("en").keys()].sort();
  const zhSlugs = [...byLocale.get("zh").keys()].sort();
  if (JSON.stringify(enSlugs) !== JSON.stringify(zhSlugs)) throw new Error("English and Chinese blog slug sets differ");
  return { byLocale, slugs: enSlugs };
}
async function renderArticle(sourceRoot, post, locale, fallback, assetRoot, imageCache) {
  const config = LANGUAGE_CONFIG[locale];
  const title = locale === "ja" && fallback ? (JAPANESE_TITLES[post.slug] || post.data.title) : post.data.title;
  let body = post.body;
  const refs = imageReferences(body);
  for (const ref of refs) if (!imageCache.has(ref.url)) imageCache.set(ref.url, await materializeImage(sourceRoot, ref.url, assetRoot));
  if (post.data.cover?.image && !imageCache.has(post.data.cover.image)) imageCache.set(post.data.cover.image, await materializeImage(sourceRoot, post.data.cover.image, assetRoot));
  for (const ref of refs) body = body.replaceAll(ref.full, `![${ref.alt}](${imageCache.get(ref.url)})`);
  body = escapeMdxProse(body);
  const cover = post.data.cover?.image ? imageCache.get(post.data.cover.image) : "";
  const bodyHasCover = cover && body.includes(`](${cover})`);
  const notice = fallback ? `\n> ${config.fallbackLabel}\n` : "";
  const coverBlock = cover && !bodyHasCover ? `\n![${post.data.cover.alt || title}](${cover})\n` : "";
  return `---\ntitle: ${yamlQuote(title)}\ndescription: ${yamlQuote(post.data.description)}\n---\n\n${config.sourceLabel} [${config.sourceAction}](${canonicalUrl(post.locale, post.slug)}).\n\n${attribution(locale, post)}\n${notice}${coverBlock}\n${body.trim()}\n`;
}
function articlePage(locale, slug) { return `${locale}/articles/${slug}`; }
function renderIndex(locale, posts) {
  const config = LANGUAGE_CONFIG[locale];
  const lines = ["---", `title: ${yamlQuote(config.introTitle)}`, `description: ${yamlQuote(config.introDescription)}`, "---", "", config.introDescription, ""];
  for (const key of ["updates", "engineering", "tutorials", "announcements"]) {
    const inGroup = posts.filter((post) => post.group === key);
    if (!inGroup.length) continue;
    lines.push(`## ${config.groups[key]}`, "");
    for (const post of inGroup) lines.push(`- [${post.title}](/${articlePage(locale, post.slug)}) — ${post.date}`);
    lines.push("");
  }
  return `${lines.join("\n").trim()}\n`;
}
function navigationTab(locale, posts) {
  const config = LANGUAGE_CONFIG[locale];
  const groups = [{ group: config.overviewGroup, pages: [`${locale}/articles/index`] }];
  for (const key of ["updates", "engineering", "tutorials", "announcements"]) {
    const pages = posts.filter((post) => post.group === key).map((post) => articlePage(locale, post.slug));
    if (pages.length) groups.push({ group: config.groups[key], pages });
  }
  return { tab: config.tab, groups };
}
async function validateGenerated(manifest) {
  const docs = JSON.parse(await readFile(path.join(ROOT, "docs.json"), "utf8"));
  const failures = [];
  const referencedImages = new Set();
  for (const locale of ARTICLE_LOCALES) {
    const config = LANGUAGE_CONFIG[locale];
    const articleRoot = path.join(ROOT, locale, "articles");
    await assertDirectoryWithoutSymlinks(articleRoot, `${locale} generated article root`);
    const language = docs.navigation.languages.find((item) => item.language === config.mintlify);
    const tabs = language?.tabs.filter((item) => item.tab === config.tab) || [];
    if (tabs.length !== 1) failures.push(`${locale}: expected exactly one ${config.tab} navigation tab, found ${tabs.length}`);
    for (const article of manifest.articles.filter((item) => item.locale === locale)) {
      const file = path.join(ROOT, `${article.page}.mdx`);
      if (!existsSync(file)) failures.push(`missing article: ${article.page}.mdx`);
      else {
        const content = await readRegularFileWithin(articleRoot, file, `${locale} generated article`, "utf8");
        for (const match of content.matchAll(/!\[[^\]]*\]\((\/images\/[^)]+)\)/g)) {
          referencedImages.add(match[1]);
          const image = path.join(ROOT, match[1].slice(1));
          if (!existsSync(image) || (await stat(image)).size === 0) failures.push(`${article.page}: missing image ${match[1]}`);
        }
      }
    }
  }
  const mirroredMetadata = await imageMetadata(ROOT);
  const mirroredImages = new Set(mirroredMetadata.map((image) => image.path));
  for (const image of mirroredImages) if (!referencedImages.has(image)) failures.push(`unreferenced mirrored image: ${image}`);
  for (const image of referencedImages) if (!mirroredImages.has(image)) failures.push(`referenced image is not mirrored: ${image}`);
  const expectedImages = new Map((manifest.images || []).map((image) => [image.path, image]));
  for (const image of mirroredMetadata) {
    const expected = expectedImages.get(image.path);
    if (!expected) failures.push(`mirrored image missing from manifest: ${image.path}`);
    else if (expected.sha256 !== image.sha256 || expected.bytes !== image.bytes) failures.push(`mirrored image digest mismatch: ${image.path}`);
  }
  for (const image of expectedImages.keys()) if (!mirroredImages.has(image)) failures.push(`manifest image is missing: ${image}`);
  if (failures.length) throw new Error(`Generated article validation failed:\n${failures.join("\n")}`);
}
async function listFiles(directory) {
  if (!existsSync(directory)) return [];
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Generated content tree must not contain symlinks: ${full}`);
    if (entry.isDirectory()) files.push(...await listFiles(full));
    else if (entry.isFile()) files.push(full);
    else throw new Error(`Generated content tree must contain only directories and regular files: ${full}`);
  }
  return files;
}
async function imageMetadata(assetRoot) {
  const metadata = [];
  for (const file of await listFiles(path.join(assetRoot, "images/articles"))) {
    const bytes = await readFile(file);
    validateImageBytes(bytes, file);
    metadata.push({
      path: `/${path.relative(assetRoot, file).split(path.sep).join("/")}`,
      sha256: createHash("sha256").update(bytes).digest("hex"),
      bytes: bytes.length,
    });
  }
  return metadata.sort((a, b) => a.path.localeCompare(b.path));
}
async function referencedImagesIn(directory) {
  const images = new Set();
  for (const file of await listFiles(directory)) {
    if (!file.endsWith(".mdx")) continue;
    const content = await readFile(file, "utf8");
    for (const match of content.matchAll(/!\[[^\]]*\]\((\/images\/articles\/[^)]+)\)/g)) images.add(match[1]);
  }
  return images;
}
async function main() {
  const args = parseArgs(process.argv.slice(2));
  const manifestPath = path.join(ROOT, "scripts/blog-articles-manifest.json");
  if (args.check && !args.source) {
    await validateGenerated(JSON.parse(await readFile(manifestPath, "utf8")));
    console.log("Generated article pages, navigation, and local images are valid.");
    return;
  }
  if (!args.source) throw new Error("Pass --source /path/to/langbot-landing-page or set LANGBOT_LANDING_REPO");
  if (!existsSync(path.join(args.source, "src/content/blog"))) throw new Error(`Not a LangBot landing repository: ${args.source}`);
  const { byLocale, slugs } = await loadPosts(args.source);
  const outputRoot = await mkdtemp(path.join(tmpdir(), "langbot-docs-article-sync-"));
  const assetRoot = args.check ? outputRoot : ROOT;
  const imageCache = new Map();
  const localePosts = new Map();
  const manifest = { source: "https://github.com/langbot-app/langbot-landing-page/tree/main/src/content/blog", articles: [] };
  for (const locale of ARTICLE_LOCALES) {
    const renderedPosts = [];
    for (const slug of slugs) {
      const localized = byLocale.get(locale).get(slug);
      const post = localized || byLocale.get("en").get(slug);
      const fallback = !localized;
      const title = locale === "ja" && fallback ? (JAPANESE_TITLES[slug] || post.data.title) : post.data.title;
      renderedPosts.push({ slug, title, date: post.data.date, group: classify(byLocale.get("en").get(slug)), fallback });
      const target = path.join(outputRoot, locale, "articles", `${slug}.mdx`);
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, await renderArticle(args.source, post, locale, fallback, assetRoot, imageCache));
      manifest.articles.push({ locale, slug, page: articlePage(locale, slug), sourceLocale: post.locale, fallback });
    }
    renderedPosts.sort((a, b) => b.date.localeCompare(a.date) || a.slug.localeCompare(b.slug));
    localePosts.set(locale, renderedPosts);
    await writeFile(path.join(outputRoot, locale, "articles", "index.mdx"), renderIndex(locale, renderedPosts));
  }
  if (!args.check) {
    const referencedImages = await referencedImagesIn(outputRoot);
    for (const file of await listFiles(path.join(ROOT, "images/articles"))) {
      const publicPath = `/${path.relative(ROOT, file).split(path.sep).join("/")}`;
      if (!referencedImages.has(publicPath)) await rm(file, { force: true });
    }
  }
  manifest.images = await imageMetadata(assetRoot);
  if (args.check) {
    const mismatches = [];
    for (const locale of ARTICLE_LOCALES) {
      const generatedDir = path.join(outputRoot, locale, "articles");
      const currentDir = path.join(ROOT, locale, "articles");
      const generatedNames = (await readdir(generatedDir)).sort();
      const currentEntries = existsSync(currentDir) ? await readdir(currentDir, { withFileTypes: true }) : [];
      if (currentEntries.some((entry) => !entry.isFile() || entry.isSymbolicLink())) mismatches.push(`${locale}/articles contains non-regular files`);
      const currentNames = currentEntries.map((entry) => entry.name).sort();
      if (JSON.stringify(generatedNames) !== JSON.stringify(currentNames)) mismatches.push(`${locale}/articles file set`);
      for (const name of generatedNames) {
        const generated = await readFile(path.join(generatedDir, name), "utf8");
        const currentFile = path.join(currentDir, name);
        const current = existsSync(currentFile) ? await readRegularFileWithin(currentDir, currentFile, `${locale} generated article`, "utf8") : "";
        if (generated !== current) mismatches.push(`${locale}/articles/${name}`);
      }
    }
    const currentManifest = existsSync(manifestPath) ? JSON.parse(await readFile(manifestPath, "utf8")) : null;
    if (JSON.stringify(currentManifest) !== JSON.stringify(manifest)) mismatches.push("scripts/blog-articles-manifest.json");
    const currentDocs = JSON.parse(await readFile(path.join(ROOT, "docs.json"), "utf8"));
    for (const locale of ARTICLE_LOCALES) {
      const config = LANGUAGE_CONFIG[locale];
      const language = currentDocs.navigation.languages.find((item) => item.language === config.mintlify);
      const matchingTabs = language?.tabs.filter((item) => item.tab === config.tab) || [];
      const currentTab = matchingTabs.length === 1 ? matchingTabs[0] : null;
      const expectedTab = navigationTab(locale, localePosts.get(locale));
      if (matchingTabs.length !== 1 || JSON.stringify(currentTab) !== JSON.stringify(expectedTab)) mismatches.push(`docs.json ${config.tab} tab`);
    }
    await rm(outputRoot, { recursive: true, force: true });
    if (mismatches.length) throw new Error(`Blog articles are out of sync:\n${mismatches.join("\n")}`);
    await validateGenerated(JSON.parse(await readFile(manifestPath, "utf8")));
    console.log(`All ${manifest.articles.length} localized article pages are synchronized.`);
    return;
  }
  for (const locale of ARTICLE_LOCALES) {
    const targetDir = path.join(ROOT, locale, "articles");
    await rm(targetDir, { recursive: true, force: true });
    await mkdir(path.dirname(targetDir), { recursive: true });
    await cp(path.join(outputRoot, locale, "articles"), targetDir, { recursive: true });
  }
  await rm(outputRoot, { recursive: true, force: true });
  const docsPath = path.join(ROOT, "docs.json");
  const docs = JSON.parse(await readFile(docsPath, "utf8"));
  for (const locale of ARTICLE_LOCALES) {
    const config = LANGUAGE_CONFIG[locale];
    const language = docs.navigation.languages.find((item) => item.language === config.mintlify);
    if (!language) throw new Error(`docs.json missing language ${config.mintlify}`);
    language.tabs = language.tabs.filter((item) => item.tab !== config.tab);
    const apiIndex = language.tabs.findIndex((item) => /API/.test(item.tab));
    language.tabs.splice(apiIndex >= 0 ? apiIndex : language.tabs.length, 0, navigationTab(locale, localePosts.get(locale)));
  }
  await writeFile(docsPath, `${JSON.stringify(docs, null, 2)}\n`);
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  await validateGenerated(manifest);
  console.log(`Synchronized ${slugs.length} posts into ${manifest.articles.length} localized Wiki pages.`);
}
main().catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });

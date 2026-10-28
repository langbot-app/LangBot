import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(import.meta.dirname, "..");
export async function generateLocaleEntry(publicRoot = path.join(root, "dist/public")) {
  const helper = await readFile(path.join(root, "src/locale-preference.mjs"), "utf8");
  // Inline a classic script: negotiation runs before rendering or module fetches.
  const script = helper.replace(/^export /gm, "") + "\nenterDocs();";
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LangBot Docs</title><script>${script}</script></head>
<body><main><h1>LangBot Docs</h1><noscript><p>Please choose a language / 请选择语言 / 言語を選択してください</p></noscript>
<ul><li><a lang="en" href="/docs/en/insight/guide">English</a></li><li><a lang="zh" href="/docs/zh/insight/guide">简体中文</a></li><li><a lang="ja" href="/docs/ja/insight/guide">日本語</a></li></ul>
</main></body></html>
`;
  await writeFile(path.join(publicRoot, "index.html"), html);
  return html;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await generateLocaleEntry();
  console.log("Generated browser-negotiated /docs/ entry (langbot-docs-locale)");
}

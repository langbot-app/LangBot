import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { LOCALES } from "../src/locale-preference.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PUBLIC_ROOT = path.join(ROOT, "dist/public");

export async function splitSearchIndex(publicRoot = PUBLIC_ROOT) {
  const searchPath = path.join(publicRoot, "api/search");
  const index = JSON.parse(await readFile(searchPath, "utf8"));
  if (index.type !== "i18n" || !index.raw || typeof index.raw !== "object") {
    throw new Error("Expected Fumapress to export a localized FlexSearch index");
  }

  const actualLocales = Object.keys(index.raw).sort();
  if (actualLocales.join(",") !== [...LOCALES].sort().join(",")) {
    throw new Error(`Unexpected search index locales: ${actualLocales.join(", ")}`);
  }

  await rm(searchPath);
  await mkdir(searchPath, { recursive: true });
  for (const locale of LOCALES) {
    const shard = { type: "i18n", raw: { [locale]: index.raw[locale] } };
    await writeFile(path.join(searchPath, `${locale}.json`), `${JSON.stringify(shard)}\n`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await splitSearchIndex();
}

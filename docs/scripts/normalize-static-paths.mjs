#!/usr/bin/env node

import { access, readdir, rename } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function decodePathSegment(segment) {
  const decoded = decodeURIComponent(segment);
  if (decoded.includes("/") || decoded.includes("\\") || decoded.includes("\0")) {
    throw new Error(`Refusing to decode unsafe output path segment: ${segment}`);
  }
  return decoded;
}

async function exists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

export async function normalizeStaticPaths(directory) {
  let renamed = 0;
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const source = path.join(directory, entry.name);
    if (entry.isDirectory()) renamed += await normalizeStaticPaths(source);

    const decodedName = decodePathSegment(entry.name);
    if (decodedName === entry.name) continue;

    const destination = path.join(directory, decodedName);
    if (await exists(destination)) {
      throw new Error(`Static output path collision: ${source} -> ${destination}`);
    }
    await rename(source, destination);
    renamed += 1;
  }
  return renamed;
}

async function main() {
  const publicRoot = path.join(ROOT, "dist/public");
  const renamed = await normalizeStaticPaths(publicRoot);
  console.log(`Normalized ${renamed} percent-encoded static path segments`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

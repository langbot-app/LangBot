#!/usr/bin/env node

import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const binDir = resolve(root, "bin");
const lbsPath = resolve(binDir, "lbs");
const wrapper = [
  "#!/usr/bin/env bash",
  "set -euo pipefail",
  "",
  'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
  'exec node "$SCRIPT_DIR/../src/lbs.ts" "$@"',
  "",
].join("\n");

await mkdir(binDir, { recursive: true });

let current = "";
try {
  current = await readFile(lbsPath, "utf8");
} catch {
  // Missing wrapper is the normal first-run path.
}

if (current !== wrapper) {
  await writeFile(lbsPath, wrapper, "utf8");
  await chmod(lbsPath, 0o755);
}

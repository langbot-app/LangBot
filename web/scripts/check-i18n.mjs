#!/usr/bin/env node
/**
 * Check that all i18n locale files have the same keys as en-US.ts (the reference).
 * Reports missing keys (present in en-US but absent in the locale) and
 * extra keys (present in the locale but absent in en-US).
 * Exits with code 1 if any mismatch is found.
 *
 * Keys are extracted using a line-by-line parser that handles the known format
 * of the locale files (no eval or dynamic code execution is used).
 */

import { readFileSync, readdirSync } from 'fs';
import { resolve, dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = resolve(__dirname, '../src/i18n/locales');
const REFERENCE = 'en-US.ts';

/**
 * Extract all dot-notation leaf keys from a TypeScript locale file.
 *
 * The expected file format is:
 *   const <varName> = {
 *     key: 'value',
 *     nested: {
 *       subKey: 'value',
 *     },
 *   };
 *   export default <varName>;
 *
 * The parser tracks indentation depth to build dot-separated key paths and
 * never executes the file content.
 */
function extractKeys(filePath) {
  let src = readFileSync(filePath, 'utf8');

  // Remove UTF-8 BOM if present
  if (src.charCodeAt(0) === 0xfeff) {
    src = src.slice(1);
  }

  const lines = src.split('\n');
  const keys = [];
  // Stack of { key, indent } pairs representing the current nesting path
  const stack = [];

  // Matches an object key at the start of a line (identifier or quoted string)
  // Captures: [indent, keyName, hasOpenBrace]
  const KEY_RE = /^(\s+)([\w]+)\s*:/;
  const OPEN_BRACE_RE = /\{\s*$/;
  const CLOSE_BRACE_RE = /^\s*\},?\s*$/;

  for (const line of lines) {
    if (CLOSE_BRACE_RE.test(line)) {
      // Pop the stack when we encounter a closing brace line
      const lineIndent = line.match(/^(\s*)/)[1].length;
      while (stack.length > 0 && stack[stack.length - 1].indent >= lineIndent) {
        stack.pop();
      }
      continue;
    }

    const m = line.match(KEY_RE);
    if (!m) continue;

    const indent = m[1].length;
    const keyName = m[2];

    // Pop stack entries that are at the same or deeper indent level
    while (stack.length > 0 && stack[stack.length - 1].indent >= indent) {
      stack.pop();
    }

    const prefix = stack.map((e) => e.key).join('.');
    const fullKey = prefix ? `${prefix}.${keyName}` : keyName;

    if (OPEN_BRACE_RE.test(line)) {
      // This is a parent (nested object) key — push onto stack, don't record as leaf
      stack.push({ key: keyName, indent });
    } else {
      // This is a leaf key
      keys.push(fullKey);
    }
  }

  return keys;
}

function main() {
  const files = readdirSync(LOCALES_DIR).filter((f) => f.endsWith('.ts'));

  if (!files.includes(REFERENCE)) {
    console.error(`Reference file ${REFERENCE} not found in ${LOCALES_DIR}`);
    process.exit(1);
  }

  const refKeys = new Set(extractKeys(join(LOCALES_DIR, REFERENCE)));
  let hasError = false;

  for (const file of files) {
    if (file === REFERENCE) continue;

    const locale = file.replace('.ts', '');
    let localeKeys;
    try {
      localeKeys = new Set(extractKeys(join(LOCALES_DIR, file)));
    } catch (e) {
      console.error(`[${locale}] Failed to parse file: ${e.message}`);
      hasError = true;
      continue;
    }

    const missing = [...refKeys].filter((k) => !localeKeys.has(k));
    const extra = [...localeKeys].filter((k) => !refKeys.has(k));

    if (missing.length === 0 && extra.length === 0) {
      console.log(`[${locale}] ✅ All keys match.`);
    } else {
      hasError = true;
      console.log(`\n[${locale}] ❌ Key mismatch detected:`);
      if (missing.length > 0) {
        console.log(`  Missing keys (in en-US but not in ${locale}):`);
        for (const k of missing) {
          console.log(`    - ${k}`);
        }
      }
      if (extra.length > 0) {
        console.log(`  Extra keys (in ${locale} but not in en-US):`);
        for (const k of extra) {
          console.log(`    + ${k}`);
        }
      }
    }
  }

  if (hasError) {
    console.log('\n❌ i18n key check failed. Please fix the mismatches above.');
    process.exit(1);
  } else {
    console.log('\n✅ All i18n locale files have matching keys.');
  }
}

main();

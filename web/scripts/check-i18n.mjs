#!/usr/bin/env node
/**
 * Check that all i18n locale files have the same keys as en-US.ts (the reference).
 * Reports missing keys (present in en-US but absent in the locale) and
 * extra keys (present in the locale but absent in en-US).
 * Exits with code 1 if any mismatch is found.
 */

import { readFileSync, readdirSync } from 'fs';
import { resolve, dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = resolve(__dirname, '../src/i18n/locales');
const REFERENCE = 'en-US.ts';

/**
 * Extract all dot-notation keys from a nested object, e.g.:
 *   { a: { b: 1, c: 2 }, d: 3 }  =>  ['a.b', 'a.c', 'd']
 */
function collectKeys(obj, prefix = '') {
  const keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...collectKeys(v, full));
    } else {
      keys.push(full);
    }
  }
  return keys;
}

/**
 * Load a TypeScript locale file by stripping the const declaration and
 * the export statement, then evaluating the object literal with Function().
 */
function loadLocale(filePath) {
  let src = readFileSync(filePath, 'utf8');

  // Remove UTF-8 BOM if present
  if (src.charCodeAt(0) === 0xfeff) {
    src = src.slice(1);
  }

  // Remove: const <name> = { ... }; — keep only the object literal part
  // Strip leading `const <identifier> = ` and trailing `export default <identifier>;`
  src = src
    .replace(/^const\s+\w+\s*=\s*/, '')   // remove `const varName = `
    .replace(/;\s*\nexport default \w+;\s*$/, '') // remove trailing `; export default varName;`
    .replace(/export default \w+;\s*$/, ''); // fallback without semicolon before export

  // eslint-disable-next-line no-new-func
  return new Function(`return (${src})`)();
}

function main() {
  const files = readdirSync(LOCALES_DIR).filter((f) => f.endsWith('.ts'));

  if (!files.includes(REFERENCE)) {
    console.error(`Reference file ${REFERENCE} not found in ${LOCALES_DIR}`);
    process.exit(1);
  }

  const refKeys = new Set(collectKeys(loadLocale(join(LOCALES_DIR, REFERENCE))));
  let hasError = false;

  for (const file of files) {
    if (file === REFERENCE) continue;

    const locale = file.replace('.ts', '');
    let localeObj;
    try {
      localeObj = loadLocale(join(LOCALES_DIR, file));
    } catch (e) {
      console.error(`[${locale}] Failed to parse file: ${e.message}`);
      hasError = true;
      continue;
    }

    const localeKeys = new Set(collectKeys(localeObj));

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

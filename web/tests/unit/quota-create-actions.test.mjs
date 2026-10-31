import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const zhPath = path.join(root, 'src/i18n/locales/zh-Hans.ts');

test('quota tooltip copy is localized in Simplified Chinese', () => {
  const source = fs.readFileSync(zhPath, 'utf8');
  assert.match(source, /createDisabledTooltip/);
  assert.match(source, /已达到.*上限/);
  assert.match(source, /删除.*后再/);
});

import assert from 'node:assert/strict';
import test from 'node:test';
import { loadLocale, locales } from './load-ts.mjs';

test('quota tooltip copy interpolates both the resource and the limit in every catalog', () => {
  for (const locale of locales) {
    const message = loadLocale(locale).limitation.createDisabledTooltip;
    assert.equal(typeof message, 'string', locale);
    assert.deepEqual(
      [...new Set(message.match(/\{\{\w+\}\}/g))].sort(),
      ['{{max}}', '{{resource}}'],
      locale,
    );
  }
});

test('Simplified Chinese quota tooltip explains the limit and how to retry', () => {
  const message = loadLocale('zh-Hans').limitation.createDisabledTooltip;
  assert.match(message, /已达到.*上限/);
  assert.match(message, /删除.*后再/);
});

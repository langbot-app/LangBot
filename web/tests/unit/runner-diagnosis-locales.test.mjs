import assert from 'node:assert/strict';
import test from 'node:test';
import { loadLocale, locales } from './load-ts.mjs';

test('Runner diagnosis and draft-safe repair have complete runtime catalogs', () => {
  const expected = ['disabled', 'draft', 'missing', 'repair', 'runtime'];
  for (const locale of locales) {
    const { runnerDiagnosis } = loadLocale(locale).agents;
    assert.ok(runnerDiagnosis, locale);
    assert.deepEqual(Object.keys(runnerDiagnosis).sort(), expected, locale);
    for (const [key, message] of Object.entries(runnerDiagnosis)) {
      assert.equal(typeof message, 'string', `${locale}.${key}`);
      assert.notEqual(message.trim(), '', `${locale}.${key}`);
      assert.doesNotMatch(message, /\{\{[^}]+\}\}/, `${locale}.${key}`);
    }
  }
});

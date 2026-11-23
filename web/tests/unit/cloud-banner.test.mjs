import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

function loadTs(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8');
  const m = { exports: {} };
  // Locale catalogs import their own sub-catalogs; those are irrelevant to the
  // keys asserted here, so every relative import resolves to an empty module.
  const requireShim = () => ({});
  new Function(
    'module',
    'exports',
    'require',
    ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    }).outputText,
  )(m, m.exports, requireShim);
  return m.exports;
}

const { cloudBannerLanguageKey, resolveCloudBannerCopy, cloudBannerSignature } =
  loadTs('../../src/lib/cloud-banner.ts');

test('language keys follow the config.yaml underscore form', () => {
  assert.equal(cloudBannerLanguageKey('zh-Hans'), 'zh_hans');
  assert.equal(cloudBannerLanguageKey('zh-Hant'), 'zh_hant');
  assert.equal(cloudBannerLanguageKey('en-US'), 'en_us');
  assert.equal(cloudBannerLanguageKey(' EN_us '), 'en_us');
  assert.equal(cloudBannerLanguageKey('ja-JP'), 'ja_jp');
});

test('configured copy wins over the built-in text for that language', () => {
  const banner = {
    content: { zh_hans: '服务维护中', en_us: 'Maintenance in progress' },
  };
  assert.equal(resolveCloudBannerCopy(banner, 'zh-Hans'), '服务维护中');
  assert.equal(
    resolveCloudBannerCopy(banner, 'zh-Hant'),
    'Maintenance in progress',
  );
});

test('missing or blank entries fall back to the translated default', () => {
  assert.equal(
    resolveCloudBannerCopy({ content: { en_us: '   ' } }, 'zh-Hans'),
    null,
  );
  assert.equal(resolveCloudBannerCopy({ content: {} }, 'en-US'), null);
  assert.equal(resolveCloudBannerCopy({ content: null }, 'en-US'), null);
});

test('a dismissal is bound to the notice that was dismissed', () => {
  const first = cloudBannerSignature({ level: 'info' }, 'alpha');
  const second = cloudBannerSignature({ level: 'maintenance' }, 'alpha');
  assert.notEqual(first, second);
  assert.equal(first, cloudBannerSignature({ level: 'info' }, 'alpha'));
});

test('every locale carries the cloud_banner copy', () => {
  const locales = [
    'en-US',
    'zh-Hans',
    'zh-Hant',
    'ja-JP',
    'th-TH',
    'vi-VN',
    'es-ES',
    'ru-RU',
  ];
  const expectedKeys = [
    'message',
    'dedicated_link',
    'cta_dedicated',
    'or',
    'self_hosted_link',
    'period',
    'dismiss',
  ];
  for (const locale of locales) {
    const translations = loadTs(`../../src/i18n/locales/${locale}.ts`).default;
    const banner = translations.cloud_banner;
    assert.ok(banner, `${locale} is missing cloud_banner`);
    assert.deepEqual(Object.keys(banner).sort(), [...expectedKeys].sort());
    for (const key of expectedKeys) {
      assert.equal(
        typeof banner[key],
        'string',
        `${locale}.cloud_banner.${key} must be a string`,
      );
    }
    assert.notEqual(banner.message.trim(), '', `${locale} message is empty`);
    // The message is followed by inline links, so a trailing period would
    // render as a stray full stop before them.
    assert.ok(
      !banner.message.trim().endsWith('.') &&
        !banner.message.trim().endsWith('。'),
      `${locale} message must not end the sentence before its links`,
    );
  }
});

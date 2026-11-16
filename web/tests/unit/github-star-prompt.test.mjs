import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

function loadTs(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8');
  const m = { exports: {} };
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
  )(m, m.exports, () => ({}));
  return m.exports;
}

const {
  STAR_PROMPT_THRESHOLD,
  shouldOfferStarPrompt,
  readStarPromptState,
  writeStarPromptState,
  formatStarCount,
} = loadTs('../../src/app/home/components/star-prompt/star-prompt-state.ts');

test('threshold is 100 handled executions', () => {
  assert.equal(STAR_PROMPT_THRESHOLD, 100);
});

test('starred and dismissed are final, snoozes expire', () => {
  const now = 1_000_000;
  assert.equal(shouldOfferStarPrompt(null, now), true);
  assert.equal(shouldOfferStarPrompt({ state: 'starred' }, now), false);
  assert.equal(shouldOfferStarPrompt({ state: 'dismissed' }, now), false);
  assert.equal(
    shouldOfferStarPrompt({ state: 'snoozed', until: now + 1 }, now),
    false,
  );
  assert.equal(
    shouldOfferStarPrompt({ state: 'snoozed', until: now - 1 }, now),
    true,
  );
  assert.equal(shouldOfferStarPrompt({ state: 'snoozed' }, now), true);
});

test('state round-trips through localStorage and tolerates junk', () => {
  const store = new Map();
  globalThis.window = {
    localStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
    },
  };
  try {
    assert.equal(readStarPromptState(), null);
    writeStarPromptState({ state: 'snoozed', until: 42 });
    assert.deepEqual(readStarPromptState(), { state: 'snoozed', until: 42 });
    store.set('langbot_github_star_prompt', '{not json');
    assert.equal(readStarPromptState(), null);
  } finally {
    delete globalThis.window;
  }
});

test('star counts use the sidebar compact format', () => {
  assert.equal(formatStarCount(987), '987');
  assert.equal(formatStarCount(56321), '56.3k');
});

test('every locale has the prompt copy with the total placeholder', () => {
  for (const locale of [
    'zh-Hans',
    'zh-Hant',
    'en-US',
    'ja-JP',
    'es-ES',
    'ru-RU',
    'th-TH',
    'vi-VN',
  ]) {
    const copy = loadTs(`../../src/i18n/locales/${locale}.ts`).default
      .githubStarPrompt;
    assert.ok(copy, locale);
    assert.match(copy.title, /\{\{total\}\}/, locale);
    for (const key of ['description', 'later', 'star', 'close']) {
      assert.ok(copy[key]?.trim(), `${locale}.${key}`);
    }
  }
});

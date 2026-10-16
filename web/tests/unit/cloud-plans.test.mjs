import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const source = readFileSync(
  new URL(
    '../../src/app/home/components/workspace-settings/cloud-plans.ts',
    import.meta.url,
  ),
  'utf8',
);
const m = { exports: {} };
new Function(
  'module',
  'exports',
  ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText,
)(m, m.exports);
const {
  cloudPlanCheckoutURL,
  cloudSubscriptionManagementURL,
  cloudPlanPrice,
  localizedPlanText,
  fetchPublicCloudPlans,
} = m.exports;

test('checkout links preserve the workspace and selection, never source credentials', () => {
  const url = new URL(
    cloudPlanCheckoutURL(
      'https://space.example/prefix?token=secret#access_token=secret',
      'workspace-1',
      'pro & team',
      'monthly',
      'JPY',
    ),
  );
  assert.equal(url.pathname, '/prefix/cloud');
  assert.equal(url.hash, '');
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    environment: 'new',
    step: 'plan',
    workspace: 'workspace-1',
    plan: 'pro & team',
    billing: 'monthly',
    currency: 'JPY',
  });
  assert.throws(() =>
    cloudPlanCheckoutURL(
      'https://user:secret@space.example',
      'w',
      'pro',
      'annual',
      'USD',
    ),
  );
  assert.throws(() =>
    cloudPlanCheckoutURL('javascript:alert(1)', 'w', 'pro', 'annual', 'USD'),
  );
});
test('prices match server annual discount and locale fallback', () => {
  const plan = { price_cny: '29', price_usd: '5.5', price_jpy: '800' };
  assert.equal(cloudPlanPrice(plan, 'monthly', 'USD'), 5.5);
  assert.equal(cloudPlanPrice(plan, 'annual', 'CNY'), 290);
  assert.equal(cloudPlanPrice(plan, 'annual', 'JPY'), 8000);
  assert.equal(
    localizedPlanText({ zh_Hans: '专业版', en_US: 'Pro' }, 'zh-Hans'),
    '专业版',
  );
  assert.equal(localizedPlanText({ en_US: 'Pro' }, 'ja-JP'), 'Pro');
  assert.throws(() =>
    cloudPlanPrice({ ...plan, price_usd: 'NaN' }, 'monthly', 'USD'),
  );
});
test('public catalog fetch omits cookies and authorization, hides inactive plans, validates response', async (t) => {
  let options, url;
  const plan = {
    uuid: '1',
    name: 'pro',
    limits: {},
    price_cny: '29',
    price_usd: '5',
    price_jpy: '800',
    is_active: true,
    subscription_disabled: true,
  };
  t.mock.method(globalThis, 'fetch', async (u, o) => {
    url = u;
    options = o;
    return {
      ok: true,
      json: async () => ({
        code: 0,
        data: [plan, { ...plan, uuid: 'hidden', is_active: false }],
      }),
    };
  });
  assert.deepEqual(
    await fetchPublicCloudPlans(
      'https://space.example',
      new AbortController().signal,
    ),
    [plan],
  );
  assert.equal(url.pathname, '/api/v1/cloud/v2/plans');
  assert.equal(options.credentials, 'omit');
  assert.equal(options.referrerPolicy, 'no-referrer');
  assert.equal(options.headers, undefined);
  globalThis.fetch = async () => ({ ok: false });
  await assert.rejects(fetchPublicCloudPlans('https://space.example'));
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({ code: 0, data: [{ ...plan, price_cny: 'broken' }] }),
  });
  await assert.rejects(fetchPublicCloudPlans('https://space.example'));
});

const platformsModule = { exports: {} };
new Function(
  'module',
  'exports',
  ts.transpileModule(
    readFileSync(
      new URL(
        '../../src/app/home/components/workspace-settings/cloud-plan-platforms.ts',
        import.meta.url,
      ),
      'utf8',
    ),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText,
)(platformsModule, platformsModule.exports);
const { supportedPlanPlatforms, KNOWN_ADAPTERS } = platformsModule.exports;
test('supported platforms hide blocked families and merge Omni variants', () => {
  const platforms = supportedPlanPlatforms([
    'aiocqhttp',
    'line',
    'discord-eba',
  ]);
  const names = platforms.map((platform) => platform.name);
  assert.equal(names.includes('aiocqhttp'), false);
  assert.equal(names.includes('LINE'), false);
  assert.equal(names.includes('discord'), true);
  assert.equal(
    names.some((name) => name.endsWith('-omni')),
    false,
  );
  assert.equal(new Set(names).size, names.length);
  assert.ok(platforms.every((platform) => platform.label && platform.icon));
  assert.deepEqual(
    supportedPlanPlatforms(KNOWN_ADAPTERS.map((adapter) => adapter.name)),
    [],
  );
  assert.deepEqual(
    supportedPlanPlatforms(['unknown-adapter']),
    supportedPlanPlatforms(),
  );
});

test('plan currency follows the current UI language', () => {
  for (const locale of ['zh-Hans', 'zh_Hans', 'zh-Hans-CN'])
    assert.equal(m.exports.cloudPlanCurrencyForLanguage(locale), 'CNY');
  for (const locale of ['ja-JP', 'ja_JP', 'ja'])
    assert.equal(m.exports.cloudPlanCurrencyForLanguage(locale), 'JPY');
  for (const locale of [
    'zh-Hant',
    'zh_Hant',
    'en-US',
    'es-ES',
    'ru-RU',
    'th-TH',
    'vi-VN',
  ])
    assert.equal(m.exports.cloudPlanCurrencyForLanguage(locale), 'USD');
});

test('subscription management links use the production environment', () => {
  const url = new URL(
    cloudSubscriptionManagementURL('https://space.example', 'w'),
  );
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    environment: 'new',
    step: 'subscription',
    workspace: 'w',
  });
});

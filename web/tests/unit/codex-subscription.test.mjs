import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

test('all locale catalogs cover Codex states and preserve the expiry placeholder', () => {
  const directory = new URL('../../src/i18n/locales/', import.meta.url);
  let expected;
  for (const file of fs.readdirSync(directory)) {
    const compiled = ts.transpileModule(
      fs.readFileSync(new URL(file, directory), 'utf8'),
      {
        compilerOptions: { module: ts.ModuleKind.CommonJS },
      },
    ).outputText;
    const module = { exports: {} };
    new Function('module', 'exports', compiled)(module, module.exports);
    const catalog = (module.exports.default || Object.values(module.exports)[0])
      .models.codex;
    const keys = Object.keys(catalog).sort();
    expected ??= keys;
    assert.deepEqual(keys, expected, file);
    assert.equal(keys.length, 26, file);
    assert.ok(catalog.expiresAt.includes('{{time}}'), file);
  }
});

function policy() {
  const source = fs.readFileSync(
    new URL(
      '../../src/app/home/components/models-dialog/component/provider-form/codexPolicy.ts',
      import.meta.url,
    ),
    'utf8',
  );
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', compiled)(module, module.exports);
  return module.exports;
}

test('Codex payload discards previously entered API credentials and URL', () => {
  const { providerPayload } = policy();
  assert.deepEqual(
    providerPayload({
      name: 'Subscription',
      requester: 'openai-codex',
      base_url: 'https://proxy.invalid',
      api_key: 'fixture-only',
    }),
    {
      name: 'Subscription',
      requester: 'openai-codex',
      base_url: 'https://chatgpt.com/backend-api/codex',
      api_keys: [],
    },
  );
});

test('ordinary providers preserve API key and base URL behavior', () => {
  assert.deepEqual(
    policy().providerPayload({
      name: 'API',
      requester: 'openai',
      base_url: 'https://api.example.test/v1',
      api_key: 'fixture-only',
    }),
    {
      name: 'API',
      requester: 'openai',
      base_url: 'https://api.example.test/v1',
      api_keys: ['fixture-only'],
    },
  );
});

test('poll delay honors upstream minimum and transient backoff', () => {
  const { pollDelay } = policy();
  assert.equal(pollDelay(5, 0), 5000);
  assert.equal(pollDelay(10, 2), 40000);
  assert.equal(pollDelay(120, 3), 120000);
  assert.equal(pollDelay(NaN, 0), 5000);
  assert.equal(pollDelay(-1, 0), 5000);
});

test('only the contracted OpenAI device authorization URL can be opened', () => {
  const { isCodexVerificationUri } = policy();
  assert.equal(
    isCodexVerificationUri('https://auth.openai.com/codex/device'),
    true,
  );
  for (const url of [
    'javascript:alert(1)',
    'https://auth.openai.com.evil.test/codex/device',
    'https://evil.test',
    'https://user@auth.openai.com/codex/device',
  ]) {
    assert.equal(isCodexVerificationUri(url), false);
  }
});

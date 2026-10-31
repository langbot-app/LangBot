import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';

const root = process.cwd();
const dialogPath = path.join(
  root,
  'src/app/home/components/qrcode-login/QrCodeLoginDialog.tsx',
);
const localeDir = path.join(root, 'src/i18n/locales');
const backendUrlPath = path.join(root, 'src/app/infra/http/backendUrl.ts');

const dialogSource = fs.readFileSync(dialogPath, 'utf8');
const { resolveBackendBaseUrl } = await import(
  `data:text/javascript;base64,${Buffer.from(
    ts.transpileModule(fs.readFileSync(backendUrlPath, 'utf8'), {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
      },
    }).outputText,
  ).toString('base64')}`
);

test('QR login resolves a proxy-root API base against the current origin', () => {
  for (const [configured, expected] of [
    [undefined, 'https://core.example'],
    ['', 'https://core.example'],
    ['/', 'https://core.example'],
    ['/proxy/', 'https://core.example/proxy'],
    ['proxy', 'https://core.example/proxy'],
    ['https://api.example/root/', 'https://api.example/root'],
  ])
    assert.equal(
      resolveBackendBaseUrl(configured, 'https://core.example///'),
      expected,
    );
});

test('WeChat QR login never reuses Feishu progress copy', () => {
  const weixinConfig = dialogSource.match(
    /weixin:\s*\{[\s\S]*?apiBase:\s*'\/api\/v1\/platform\/adapters\/weixin\/login'/,
  )?.[0];
  assert.ok(weixinConfig, 'WeChat platform config is missing');
  assert.match(weixinConfig, /connectingKey:\s*'weixin\.connecting'/);
  assert.match(weixinConfig, /waitingKey:\s*'weixin\.waitingForScan'/);
  assert.match(weixinConfig, /retryKey:\s*'weixin\.retry'/);
  assert.doesNotMatch(weixinConfig, /feishu\./);

  for (const locale of [
    'en-US.ts',
    'es-ES.ts',
    'ja-JP.ts',
    'ru-RU.ts',
    'th-TH.ts',
    'vi-VN.ts',
    'zh-Hans.ts',
    'zh-Hant.ts',
  ]) {
    const source = fs.readFileSync(path.join(localeDir, locale), 'utf8');
    const block = source.match(/weixin:\s*\{[\s\S]*?\n\s*\},/)?.[0];
    assert.ok(block, `${locale} is missing the WeChat locale block`);
    for (const key of ['connecting', 'waitingForScan', 'retry']) {
      assert.match(
        block,
        new RegExp(`\\b${key}:`),
        `${locale} is missing weixin.${key}`,
      );
    }
  }
});

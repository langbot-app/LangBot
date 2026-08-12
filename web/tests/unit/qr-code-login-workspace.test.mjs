import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const dialogPath = path.join(
  root,
  'src/app/home/components/qrcode-login/QrCodeLoginDialog.tsx',
);
const localeDir = path.join(root, 'src/i18n/locales');

const dialogSource = fs.readFileSync(dialogPath, 'utf8');

test('QR credential exchanges preserve the active Workspace scope', () => {
  assert.match(dialogSource, /getActiveWorkspaceUuid/);
  assert.match(
    dialogSource,
    /sessionWorkspaceUuidRef\.current = workspaceUuid/,
  );
  assert.match(
    dialogSource,
    /const workspaceUuid = sessionWorkspaceUuidRef\.current/,
  );
  assert.match(dialogSource, /sessionApiBaseRef\.current = cfg\.apiBase/);
  assert.match(
    dialogSource,
    /`\$\{baseUrlRef\.current\}\$\{sessionApiBaseRef\.current\}\/\$\{sessionIdRef\.current\}`/,
  );
  assert.match(dialogSource, /'X-Workspace-Id': workspaceUuid/);

  const workspaceHeaderUses = dialogSource.match(
    /'X-Workspace-Id': workspaceUuid/g,
  );
  assert.equal(
    workspaceHeaderUses?.length,
    4,
    'start, poll, expiry cleanup, and dialog cleanup must all retain Workspace scope',
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

import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';

const localeDir = new URL('../../src/i18n/locales/', import.meta.url);
const localeFiles = readdirSync(localeDir).filter((name) =>
  name.endsWith('.ts'),
);

const deprecatedAccountCopy = [
  /Initialize with Space/i,
  /Login with Space/i,
  /Logging in with Space/i,
  /Space login/i,
  /Space accounts?/i,
  /Bind Space Account/i,
  /Authorize with Space/i,
  /通过 Space 登录/,
  /使用 Space 登录/,
  /Space 登录/,
  /Space 账户/,
  /Space 帳戶/,
  /绑定 Space/,
  /綁定 Space/,
  /Space アカウント/,
  /Space でログイン/,
  /cuenta de Space/i,
  /cuentas de Space/i,
  /cuenta Space/i,
  /tài khoản Space/i,
  /บัญชี Space/,
  /аккаунт(?:ов|а)? Space/i,
  /аккаунт Space/i,
];

test('user-facing account authentication copy uses LangBot Account terminology', () => {
  const violations = [];

  for (const file of localeFiles) {
    const source = readFileSync(new URL(file, localeDir), 'utf8');
    for (const pattern of deprecatedAccountCopy) {
      if (pattern.test(source)) violations.push(`${file}: ${pattern}`);
    }
  }

  assert.deepEqual(violations, []);
});

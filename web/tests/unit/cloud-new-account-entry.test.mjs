import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(
  new URL('../../src/app/login/page.tsx', import.meta.url),
  'utf8',
);

test('normal Cloud login starts stateful Space OAuth', () => {
  assert.match(source, /getSpaceAuthorizeUrl\(redirectUri\)/);
  assert.doesNotMatch(source, /cloudEntry/);
});

test('invitation login remains on the OAuth callback path', () => {
  assert.match(source, /getPendingInvitationToken\(\)/);
  assert.match(source, /getSpaceAuthorizeUrl\(redirectUri\)/);
});

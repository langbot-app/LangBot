import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(
  new URL('../../src/app/login/page.tsx', import.meta.url),
  'utf8',
);

test('normal Cloud login uses the standard Space OAuth callback path', () => {
  assert.doesNotMatch(source, /cloudEntry/);
  assert.match(source, /getSpaceAuthorizeUrl\(redirectUri\)/);
});

test('invitation login uses the same OAuth callback before accepting the invitation', () => {
  assert.doesNotMatch(source, /cloudEntry/);
  assert.match(source, /const invitationToken = getPendingInvitationToken\(\)/);
  assert.match(source, /acceptWorkspaceInvitation\(invitationToken\)/);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

test('invited local registration returns to login instead of authenticating', () => {
  const source = read('src/app/invitations/accept/page.tsx');
  assert.doesNotMatch(
    source,
    /beginAuthenticatedSession\([\s\S]{0,120}response\.token/,
  );
  assert.match(source, /navigate\('\/login\?invitation=1'/);
});

test('authenticated invitation page offers logout while retaining invitation', () => {
  const source = read('src/app/invitations/accept/page.tsx');
  assert.match(source, /workspace\.logoutAndReturn/);
  assert.match(source, /setPendingInvitationToken\(token\)/);
});

test('Space OAuth callback distinguishes unknown and unbound accounts by stable codes', () => {
  const source = read('src/app/auth/space/callback/page.tsx');
  assert.match(source, /space_account_not_registered/);
  assert.match(source, /space_account_binding_required/);
});

test('models panel derives LangBot Models billing state from workspace owner', () => {
  const source = read('src/app/home/components/models-dialog/ModelsPanel.tsx');
  assert.match(source, /getWorkspaceSpaceBilling/);
  assert.doesNotMatch(source, /getSpaceCredits\(\)/);
  assert.match(source, /membership\.role === 'owner'/);
});

test('provider card represents owner and member owner-bound states explicitly', () => {
  const source = read(
    'src/app/home/components/models-dialog/components/ProviderCard.tsx',
  );
  assert.match(source, /isWorkspaceOwner/);
  assert.match(source, /ownerSpaceBound/);
  assert.match(source, /models\.ownerMustBindSpace/);
  assert.match(source, /models\.usesOwnerSpaceBilling/);
});

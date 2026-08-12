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

test('support-admin launch stores a scoped principal instead of starting an Account session', () => {
  const callback = read('src/app/auth/space/callback/page.tsx');
  assert.match(callback, /response\.principal_type === 'support_admin'/);
  assert.match(
    callback,
    /beginSupportAdminSession\(response\.token, response\.workspace_uuid\)/,
  );
});

test('support-admin workspace bootstrap never calls Account bootstrap', () => {
  const source = read('src/app/infra/http/index.ts');
  assert.match(source, /export function beginSupportAdminSession/);
  assert.match(source, /export function isSupportAdminSession\(\): boolean/);
  const supportBranch = source.indexOf('if (isSupportAdminSession())');
  const accountBootstrap = source.indexOf(
    'backendClient.getWorkspaceBootstrap()',
  );
  assert.ok(supportBranch >= 0);
  assert.ok(accountBootstrap > supportBranch);
  assert.match(
    source.slice(supportBranch, accountBootstrap),
    /initializeWorkspaceInfo\([\s\S]*status: 'ready'/,
  );
  assert.match(
    source,
    /localStorage\.setItem\('authPrincipalType', 'support_admin'\)/,
  );
  const homeLayout = read('src/app/home/layout.tsx');
  assert.match(homeLayout, /!isSupportAdminSession\(\)/);
});

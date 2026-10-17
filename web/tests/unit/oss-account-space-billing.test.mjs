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

test('workspace member controls never offer ownership transfer', () => {
  const source = read(
    'src/app/home/components/workspace-settings/WorkspaceSettingsPanel.tsx',
  );
  assert.doesNotMatch(source, /canTransferOwner/);
  assert.doesNotMatch(source, /workspace\.transferOwnership/);
  assert.doesNotMatch(source, /<SelectItem value="owner">/);
});

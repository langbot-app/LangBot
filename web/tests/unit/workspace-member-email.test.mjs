import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const panelSource = await readFile(
  new URL(
    '../../src/app/home/components/workspace-settings/WorkspaceSettingsPanel.tsx',
    import.meta.url,
  ),
  'utf8',
);
const entitySource = await readFile(
  new URL('../../src/app/infra/entities/workspace.ts', import.meta.url),
  'utf8',
);

test('workspace member rows show display name, email, and role', () => {
  assert.match(entitySource, /display_name:\s*string/);
  assert.match(panelSource, /\{member\.display_name\}/);
  assert.match(
    panelSource,
    /<ItemDescription[^>]*>[\s\S]*?\{member\.email\}[\s\S]*?workspace\.roles\.\$\{member\.role\}[\s\S]*?<\/ItemDescription>/,
  );
});

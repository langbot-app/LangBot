import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(currentDirectory, '../..');

function readSource(relativePath) {
  return fs.readFileSync(path.join(webRoot, relativePath), 'utf8');
}

const homeSidebarSource = readSource(
  'src/app/home/components/home-sidebar/HomeSidebar.tsx',
);
test('hides the entire workspace switcher slot for a singleton local workspace', () => {
  assert.match(homeSidebarSource, /useWorkspaceBootstrap/);
  assert.match(
    homeSidebarSource,
    /const showWorkspaceSwitcher\s*=\s*workspaces\.length\s*>\s*1\s*\|\|\s*currentWorkspace\?\.workspace\.source\s*===\s*'cloud_projection'/,
  );
  assert.match(
    homeSidebarSource,
    /\{showWorkspaceSwitcher\s*&&\s*\(\s*<div className="px-2[^>]*>\s*<WorkspaceSwitcher/,
  );
});

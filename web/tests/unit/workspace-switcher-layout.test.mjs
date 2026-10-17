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

const homeLayoutSource = readSource('src/app/home/layout.tsx');
const homeSidebarSource = readSource(
  'src/app/home/components/home-sidebar/HomeSidebar.tsx',
);
const workspaceSettingsPanelSource = readSource(
  'src/app/home/components/workspace-settings/WorkspaceSettingsPanel.tsx',
);
test('renders WorkspaceSwitcher only from HomeSidebar', () => {
  assert.doesNotMatch(homeLayoutSource, /<WorkspaceSwitcher\b/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /<WorkspaceSwitcher\b/);
  assert.equal(homeSidebarSource.match(/<WorkspaceSwitcher\b/g)?.length, 1);
});

test('keeps Cloud workspace member management in Workspace Settings', () => {
  assert.match(workspaceSettingsPanelSource, /workspace\.inviteMember/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /#workspace-members/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /cloudMembersURL/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /canManageCloudMembers/);
});

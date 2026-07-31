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
const workspaceSwitcherSource = readSource(
  'src/app/home/components/workspace-settings/WorkspaceSwitcher.tsx',
);

test('renders WorkspaceSwitcher only from HomeSidebar', () => {
  assert.doesNotMatch(homeLayoutSource, /<WorkspaceSwitcher\b/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /<WorkspaceSwitcher\b/);
  assert.equal(homeSidebarSource.match(/<WorkspaceSwitcher\b/g)?.length, 1);
});

test('places WorkspaceSwitcher between the sidebar header and Home navigation', () => {
  const headerEnd = homeSidebarSource.indexOf('</SidebarHeader>');
  const switcher = homeSidebarSource.indexOf('<WorkspaceSwitcher');
  const contentStart = homeSidebarSource.indexOf('<SidebarContent');
  const homeGroup = homeSidebarSource.indexOf(
    "<SidebarGroupLabel>{t('sidebar.home')}</SidebarGroupLabel>",
  );

  assert.notEqual(headerEnd, -1);
  assert.notEqual(switcher, -1);
  assert.notEqual(contentStart, -1);
  assert.notEqual(homeGroup, -1);
  assert.ok(
    headerEnd < switcher,
    'WorkspaceSwitcher must follow SidebarHeader',
  );
  assert.ok(
    switcher < contentStart && switcher < homeGroup,
    'WorkspaceSwitcher must precede SidebarContent and the Home group',
  );
});

test('shows WorkspaceSwitcher for a current Cloud or OSS workspace even when it is the only workspace', () => {
  assert.match(
    workspaceSwitcherSource,
    /if \(!currentWorkspace\) return null;/,
  );
  assert.doesNotMatch(workspaceSwitcherSource, /workspaces\.length\s*<=\s*1/);
  assert.doesNotMatch(
    homeSidebarSource,
    /currentWorkspace\?\.workspace\.source\s*===\s*'cloud_projection'[\s\S]{0,200}<WorkspaceSwitcher/,
  );
});

test('keeps Cloud workspace member management in Workspace Settings', () => {
  assert.match(workspaceSettingsPanelSource, /workspace\.inviteMember/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /#workspace-members/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /cloudMembersURL/);
  assert.doesNotMatch(workspaceSettingsPanelSource, /canManageCloudMembers/);
});

test('keeps workspace plan and settings controls on the workspace row', () => {
  assert.match(workspaceSwitcherSource, /entry\.plan_name/);
  assert.match(
    workspaceSwitcherSource,
    /aria-label=\{t\('workspace\.settings'\)\}/,
  );
  assert.match(workspaceSwitcherSource, /className="size-8"/);
  assert.doesNotMatch(workspaceSwitcherSource, /workspace\.currentPlan/);
  assert.doesNotMatch(workspaceSwitcherSource, /workspace\.upgradePlan/);
  assert.doesNotMatch(workspaceSwitcherSource, /workspace\.roles/);
  assert.doesNotMatch(workspaceSwitcherSource, /entry\.membership\.role/);
});

test('moves Cloud plan upgrades into Workspace Settings', () => {
  assert.match(workspaceSettingsPanelSource, /workspace\.upgradePlan/);
  assert.match(workspaceSettingsPanelSource, /cloudPortalURL/);
  assert.match(workspaceSettingsPanelSource, /step=plan/);
  assert.match(workspaceSettingsPanelSource, /systemInfo\.cloud_service_url/);
});

test('aligns the workspace trigger with navigation entries on both sides and truncates long names', () => {
  assert.match(
    homeSidebarSource,
    /<div className="px-2[^>]*>[\s\S]*<WorkspaceSwitcher className="w-full/,
  );
  assert.doesNotMatch(
    homeSidebarSource,
    /WorkspaceSwitcher className="[^"]*w-4\/5/,
  );
  assert.match(workspaceSwitcherSource, /h-9/);
  assert.match(workspaceSwitcherSource, /w-64/);
  assert.doesNotMatch(workspaceSwitcherSource, /min-w-80/);
  assert.match(workspaceSwitcherSource, /max-w-\[7rem\][^>]*truncate/);
});

test('uses an infrastructure-level Box health endpoint in monitoring', () => {
  const statusCardSource = readSource(
    'src/app/home/monitoring/components/overview-cards/SystemStatusCards.tsx',
  );
  const backendClientSource = readSource('src/app/infra/http/BackendClient.ts');
  assert.match(backendClientSource, /getBoxRuntimeStatus/);
  assert.match(statusCardSource, /getBoxRuntimeStatus/);
});

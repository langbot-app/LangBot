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
const botFormSource = readSource(
  'src/app/home/bots/components/bot-form/BotForm.tsx',
);
const dynamicFormSource = readSource(
  'src/app/home/components/dynamic-form/DynamicFormComponent.tsx',
);
const kbFormSource = readSource(
  'src/app/home/knowledge/components/kb-form/KBForm.tsx',
);
const settingsDialogSource = readSource(
  'src/app/home/components/settings-dialog/SettingsDialog.tsx',
);
const pluginPageSource = readSource('src/app/home/plugin-pages/page.tsx');
const authenticatedPluginResourceSource = readSource(
  'src/hooks/useAuthenticatedPluginResource.ts',
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

test('keeps bot forms spaced with responsive setup and detail columns', () => {
  const fieldset = botFormSource.match(
    /<fieldset\s[\s\S]*?disabled=\{isLoading\}/,
  )?.[0];
  assert.ok(fieldset, 'the form must retain its loading-disabled fieldset');
  assert.match(
    fieldset,
    /initBotId\s*\?\s*'grid gap-4 lg:h-full lg:min-h-0 lg:grid-cols-\[minmax\(0,2fr\)_minmax\(0,3fr\)\] lg:grid-rows-\[minmax\(0,1fr\)\]'\s*:\s*'grid items-start gap-6 lg:grid-cols-\[minmax\(16rem,0\.7fr\)_minmax\(0,2fr\)\]'/,
  );
  assert.match(kbFormSource, /<form[\s\S]*?className="space-y-6"/);
});

test('hides the manifest connection switch behind the dedicated selector', () => {
  assert.match(
    botFormSource,
    /webhookField\?\.show_if\?\.field\s*\?\s*\[webhookField\.show_if\.field\]/,
  );
  assert.match(
    botFormSource,
    /hiddenItemNames=\{connectionModeControllerNames\}/,
  );
  assert.match(
    dynamicFormSource,
    /if \(hiddenItemNames\?\.includes\(config\.name\)\) return null/,
  );
  assert.doesNotMatch(
    dynamicFormSource.match(
      /const editableItems = useMemo\([\s\S]*?\n  \);/,
    )?.[0] ?? '',
    /hiddenItemNames/,
  );
});

test('does not expose storage analysis in Cloud settings or via a deep link', () => {
  assert.match(
    homeSidebarSource,
    /canViewStorageAnalysis\s*&&\s*\(\s*<DropdownMenuItem[\s\S]*?openSettings\('storageAnalysis'\)/,
  );
  assert.match(
    settingsDialogSource,
    /const canViewStorageAnalysis\s*=\s*currentWorkspace\?\.workspace\.source\s*!==\s*'cloud_projection'\s*&&\s*canViewAudit/,
  );
  assert.match(
    settingsDialogSource,
    /item\.id === 'storageAnalysis'[\s\S]*?return canViewStorageAnalysis/,
  );
  assert.match(
    settingsDialogSource,
    /section === 'storageAnalysis' && !canViewStorageAnalysis/,
  );
  assert.match(
    settingsDialogSource,
    /section === 'storageAnalysis' &&\s*canViewStorageAnalysis &&\s*\(\s*<StorageAnalysisPanel/,
  );
});

test('renders storage analysis with the storage icon in the user menu', () => {
  assert.match(
    homeSidebarSource,
    /canViewStorageAnalysis\s*&&\s*\(\s*<DropdownMenuItem[\s\S]*?<HardDrive\s*\/>[\s\S]*?\{t\('storageAnalysis\.title'\)\}/,
  );
});

test('loads plugin pages through the authenticated Workspace-scoped asset route', () => {
  assert.match(pluginPageSource, /useAuthenticatedPluginAsset/);
  assert.match(
    pluginPageSource,
    /useAuthenticatedPluginAsset\(\s*author,\s*pluginName,\s*pagePath,?\s*\)/,
  );
  assert.match(pluginPageSource, /src=\{assetUrl\}/);
  assert.doesNotMatch(pluginPageSource, /getPluginAssetURL\(/);
  assert.match(pluginPageSource, /plugins\.loadFailed/);
  assert.match(pluginPageSource, /loadedAssetUrl !== assetUrl/);
});

test('revokes and reloads authenticated plugin resources when the Workspace changes', () => {
  assert.match(authenticatedPluginResourceSource, /useCurrentWorkspace/);
  assert.match(
    authenticatedPluginResourceSource,
    /const workspaceUuid = currentWorkspace\?\.workspace\.uuid;/,
  );
  assert.match(
    authenticatedPluginResourceSource,
    /\[author, name, filepath, resourceKey\]/,
  );
  assert.match(
    authenticatedPluginResourceSource,
    /resource\.key === resourceKey \? resource\.url : ''/,
  );
});

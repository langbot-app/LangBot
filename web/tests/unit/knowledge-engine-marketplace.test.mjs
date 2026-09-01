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

const kbFormSource = readSource(
  'src/app/home/knowledge/components/kb-form/KBForm.tsx',
);
const selectSource = readSource(
  'src/app/home/knowledge/components/kb-form/KnowledgeEngineSelect.tsx',
);
const agentRunnerSelectSource = readSource(
  'src/app/home/agents/components/AgentRunnerSelect.tsx',
);
const agentFormSource = readSource(
  'src/app/home/agents/components/AgentFormComponent.tsx',
);
const pipelineFormSource = readSource(
  'src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx',
);
const agentRunnerMarketplaceSource = readSource(
  'src/app/home/agents/agent-runner-marketplace.ts',
);
const marketplaceInstallButtonSource = readSource(
  'src/app/home/components/MarketplaceInstallButton.tsx',
);
const marketplaceSource = readSource(
  'src/app/home/knowledge/components/kb-form/knowledge-engine-marketplace.ts',
);
const taskContextSource = readSource(
  'src/app/home/plugins/components/plugin-install-task/PluginInstallTaskContext.tsx',
);
const progressDialogSource = readSource(
  'src/app/home/plugins/components/plugin-install-task/PluginInstallProgressDialog.tsx',
);
const installedPluginsSource = readSource(
  'src/app/home/plugins/components/plugin-installed/PluginInstalledComponent.tsx',
);
const homeSidebarSource = readSource(
  'src/app/home/components/home-sidebar/HomeSidebar.tsx',
);

test('keeps the knowledge-base fields visible without an installed engine', () => {
  assert.match(kbFormSource, /<KnowledgeEngineSelect/);
  assert.match(kbFormSource, /name="name"/);
  assert.match(kbFormSource, /name="description"/);
  assert.doesNotMatch(kbFormSource, /if \(ragEngines\.length === 0\)/);
});

test('offers KnowledgeEngine marketplace plugins inside the selector', () => {
  assert.match(
    marketplaceSource,
    /KNOWLEDGE_ENGINE_COMPONENT_FILTER = 'KnowledgeEngine'/,
  );
  assert.match(marketplaceSource, /installPluginFromMarketplace\(/);
  assert.match(marketplaceSource, /getKnowledgeEngines\(\)/);
  assert.match(marketplaceSource, /sessionStorage\.setItem\(/);
  assert.match(selectSource, /resumePendingKnowledgeEngineInstall\(/);
  assert.match(selectSource, /onInstalled\(installed\)/);
  assert.match(selectSource, /component=KnowledgeEngine/);
});

test('tracks plugin upgrades as recoverable multistep async tasks', () => {
  assert.match(taskContextSource, /name\.startsWith\('plugin-upgrade-'\)/);
  assert.match(taskContextSource, /operation: PluginTaskOperation/);
  assert.match(taskContextSource, /progress_percent/);
  assert.match(progressDialogSource, /InstallStage\.CHECKING/);
  assert.match(progressDialogSource, /InstallStage\.VALIDATING/);
  assert.match(progressDialogSource, /InstallStage\.ACTIVATING/);
  assert.match(progressDialogSource, /plugins\.installProgress\.updateTitle/);
  for (const source of [installedPluginsSource, homeSidebarSource]) {
    assert.match(
      source,
      /upgradePlugin\([\s\S]*?add(?:Plugin)?Task\([\s\S]*?operation: 'upgrade'/,
    );
    assert.match(
      source,
      /pluginTaskKey\(res\.task_id, 'marketplace', 'upgrade'\)/,
    );
  }
});

test('keeps marketplace install actions on one fixed vertical column', () => {
  for (const source of [selectSource, agentRunnerSelectSource]) {
    assert.match(source, /grid-cols-\[1\.75rem_minmax\(0,1fr\)_4rem\]/);
    assert.match(source, /<MarketplaceInstallButton/);
  }
  assert.match(marketplaceInstallButtonSource, /justify-self-end/);
});

test('uses a compact selected engine layout and clears stale required errors', () => {
  assert.match(selectSource, /function SelectedEngineContent/);
  assert.match(
    selectSource,
    /selectedEngine \? \([\s\S]*?<SelectedEngineContent engine=\{selectedEngine\}/,
  );
  assert.match(
    selectSource,
    /flex min-w-0 flex-1 items-center gap-2 text-left/,
  );
  assert.match(kbFormSource, /form\.clearErrors\('ragEngineId'\)/);
  assert.match(kbFormSource, /form\.trigger\('ragEngineId'\)/);
  assert.doesNotMatch(kbFormSource, /field\.onChange\(value\)/);
});

test('installs marketplace components from inline progress buttons without selecting them', () => {
  for (const source of [selectSource, agentRunnerSelectSource]) {
    assert.match(source, /const handleInstall = useCallback/);
    assert.match(source, /installing=\{activePluginId === pluginId\}/);
    assert.match(source, /progress=\{installProgress\}/);
    assert.doesNotMatch(source, /MARKETPLACE_VALUE_PREFIX/);
  }
  assert.match(marketplaceInstallButtonSource, /<Progress/);
  assert.match(marketplaceInstallButtonSource, /onPointerDown=/);
  assert.match(kbFormSource, /suppressNextAutoSelectRef\.current = true/);
  assert.doesNotMatch(
    kbFormSource,
    /handleEngineInstalled[\s\S]*?handleEngineChange\(engine\.plugin_id/,
  );
  for (const source of [agentFormSource, pipelineFormSource]) {
    const callback = source.match(
      /const applyInstalledRunner = useCallback\(([\s\S]*?)\n  \);/,
    );
    assert.ok(callback);
    assert.doesNotMatch(callback[1], /form\.setValue/);
  }
});

test('shows plugin descriptions for installed AgentRunner entries', () => {
  assert.match(agentRunnerMarketplaceSource, /installedPluginDescriptions/);
  assert.match(agentRunnerMarketplaceSource, /metadata\.description/);
  assert.match(agentRunnerSelectSource, /installedRunnerDescription\(/);
  assert.match(
    agentRunnerSelectSource,
    /function InstalledRunnerOptionContent/,
  );
  assert.match(agentRunnerSelectSource, /marketplacePlugin\?\.description/);
  assert.match(
    agentRunnerSelectSource,
    /grid-cols-\[1\.75rem_minmax\(0,1fr\)\]/,
  );
  assert.doesNotMatch(agentRunnerSelectSource, /description=\{option\.name\}/);
});

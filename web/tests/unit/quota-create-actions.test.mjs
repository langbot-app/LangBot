import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const quotaPath = path.join(
  root,
  'src/app/home/components/workspace-quota/useWorkspaceQuotaStatus.ts',
);
const sidebarPath = path.join(
  root,
  'src/app/home/components/home-sidebar/HomeSidebar.tsx',
);
const tooltipPath = path.join(
  root,
  'src/app/home/components/workspace-quota/WorkspaceQuotaTooltip.tsx',
);
const baseTooltipPath = path.join(root, 'src/components/ui/tooltip.tsx');
const addExtensionPath = path.join(root, 'src/app/home/add-extension/page.tsx');
const marketPath = path.join(
  root,
  'src/app/home/plugins/components/plugin-market/PluginMarketComponent.tsx',
);
const marketCardPath = path.join(
  root,
  'src/app/home/plugins/components/plugin-market/plugin-market-card/PluginMarketCardComponent.tsx',
);
const recommendationPath = path.join(
  root,
  'src/app/home/plugins/components/plugin-market/RecommendationLists.tsx',
);
const zhPath = path.join(root, 'src/i18n/locales/zh-Hans.ts');

test('workspace quota hook exposes reached states for every creatable resource', () => {
  assert.equal(
    fs.existsSync(quotaPath),
    true,
    'workspace quota hook is missing',
  );
  const source = fs.readFileSync(quotaPath, 'utf8');
  for (const token of [
    'botsReached',
    'pipelinesReached',
    'knowledgeBasesReached',
    'extensionsReached',
    'max_bots',
    'max_pipelines',
    'max_knowledge_bases',
    'max_extensions',
  ]) {
    assert.match(source, new RegExp(token));
  }
});

test('sidebar quota-disables create controls and renders a tooltip', () => {
  const source = fs.readFileSync(sidebarPath, 'utf8');
  const tooltip = fs.readFileSync(tooltipPath, 'utf8');
  const baseTooltip = fs.readFileSync(baseTooltipPath, 'utf8');
  assert.match(source, /useWorkspaceQuotaStatus/);
  assert.match(source, /quota\.disabled/);
  assert.match(source, /disabled=\{quota\.disabled\}/);
  assert.match(source, /WorkspaceQuotaTooltip/);
  assert.match(tooltip, /TooltipContent/);
  assert.match(tooltip, /limitation\.createDisabledTooltip/);
  assert.match(tooltip, /limitation\.quotaLoadingTooltip/);
  assert.match(tooltip, /tabIndex=\{0\}/);
  assert.match(tooltip, /max-w-72 text-left/);
  assert.doesNotMatch(tooltip, /text-center/);
  assert.doesNotMatch(baseTooltip, /text-balance/);
  assert.match(source, /config\.id === 'add-extension'/);
  assert.doesNotMatch(
    source,
    /config\.id === 'add-extension'\s*\?\s*quotaStatus\.extensions/,
  );
});

test('add-extension page disables all install entry points at the quota', () => {
  const page = fs.readFileSync(addExtensionPath, 'utf8');
  const market = fs.readFileSync(marketPath, 'utf8');
  const card = fs.readFileSync(marketCardPath, 'utf8');
  const recommendations = fs.readFileSync(recommendationPath, 'utf8');

  assert.match(page, /extensionsReached/);
  assert.match(page, /installDisabled=\{extensionsReached\}/);
  assert.match(page, /disabled=\{extensionsReached/);
  assert.match(page, /limitation\.createDisabledTooltip/);
  assert.match(market, /installDisabled/);
  assert.match(card, /installDisabled/);
  assert.match(card, /disabled=\{installDisabled\}/);
  assert.match(card, /TooltipContent/);
  assert.match(card, /max-w-72 text-left/);
  assert.doesNotMatch(card, /max-w-72 text-center/);
  assert.match(recommendations, /installDisabled=\{installDisabled\}/);
  assert.match(
    recommendations,
    /installDisabledTooltip=\{installDisabledTooltip\}/,
  );
  assert.match(page, /quota=\{extensionQuota\}/);
});

test('extension confirmation checks fail closed and enter an in-flight state first', () => {
  const page = fs.readFileSync(addExtensionPath, 'utf8');

  assert.match(page, /limitation\.quotaCheckFailed/);
  assert.doesNotMatch(page, /If we can't check, let backend handle it/);
  assert.match(
    page,
    /setGithubInstallStatus\(GithubInstallStatus\.INSTALLING\);\s+if \(!\(await checkExtensionsLimit\(\)\)\)/,
  );
  assert.match(
    page,
    /setGithubInstallStatus\(GithubInstallStatus\.SKILL_INSTALLING\);\s+if \(!\(await checkExtensionsLimit\(\)\)\)/,
  );
});

test('quota tooltip copy is localized in Simplified Chinese', () => {
  const source = fs.readFileSync(zhPath, 'utf8');
  assert.match(source, /createDisabledTooltip/);
  assert.match(source, /已达到.*上限/);
  assert.match(source, /删除.*后再/);
});

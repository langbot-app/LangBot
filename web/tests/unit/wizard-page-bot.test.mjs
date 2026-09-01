import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const wizardSource = fs.readFileSync(
  path.resolve(currentDirectory, '../../src/app/wizard/page.tsx'),
  'utf8',
);
const runnerMarketplaceSource = fs.readFileSync(
  path.resolve(
    currentDirectory,
    '../../src/app/home/agents/agent-runner-marketplace.ts',
  ),
  'utf8',
);
const widgetSource = fs.readFileSync(
  path.resolve(
    currentDirectory,
    '../../../src/langbot/templates/embed/widget.js',
  ),
  'utf8',
);

test('shows the test-only notice only when the wizard opts in', () => {
  assert.match(
    wizardSource,
    /widget\.js\?preview=wizard&v=\$\{Date\.now\(\)\}/,
  );
  assert.match(wizardSource, /script\.dataset\.testNotice = testNotice/);
  assert.match(
    wizardSource,
    /testNotice=\{t\('wizard\.botConfig\.pageBotTestNotice'\)\}/,
  );
  assert.match(widgetSource, /getAttribute\("data-test-notice"\)/);
  assert.match(widgetSource, /if \(scriptTestNotice\)/);
  assert.match(widgetSource, /testNotice\.textContent = scriptTestNotice/);
});

test('opens the Page Bot preview after every successful wizard save', () => {
  assert.match(wizardSource, /script\.dataset\.autoOpen = 'true'/);
  assert.match(
    wizardSource,
    /setPageBotPreviewRequest\(\(request\) => request \+ 1\)/,
  );
  assert.match(wizardSource, /root\?\.langbotOpen\?\.\(\)/);
  assert.match(widgetSource, /getAttribute\("data-auto-open"\) === "true"/);
  assert.match(widgetSource, /root\.langbotOpen = function \(\)/);
  assert.match(widgetSource, /if \(scriptAutoOpen\) root\.langbotOpen\(\)/);
});

test('binds every message-reply bot to its provisional pipeline before verification', () => {
  assert.match(
    wizardSource,
    /selectedScenarioDefinition\?\.processorKind === 'pipeline'[\s\S]*?httpClient\.createPipeline\(/,
  );
  assert.match(
    wizardSource,
    /event_pattern: selectedScenarioDefinition\.eventType,[\s\S]*?target_type: 'pipeline',[\s\S]*?target_uuid: previewPipelineUuid/,
  );
  assert.doesNotMatch(
    wizardSource,
    /selectedAdapter === 'web_page_bot' && !previewPipelineUuid/,
  );
});

test('keeps the 4.11 AgentRunner marketplace installation flow', () => {
  assert.match(wizardSource, /loadAgentRunnerCatalog\(\)/);
  assert.match(
    wizardSource,
    /installMarketplaceAgentRunner\(plugin, \{[\s\S]*?scope: WIZARD_RUNNER_INSTALL_SCOPE/,
  );
  assert.match(wizardSource, /resumePendingAgentRunnerInstall\(/);
  assert.match(
    runnerMarketplaceSource,
    /RUNNER_COMPONENT_FILTER = 'AgentRunner'/,
  );
  assert.match(runnerMarketplaceSource, /installPluginFromMarketplace\(/);
  assert.match(runnerMarketplaceSource, /const prefix = runnerPluginPrefix\(\{/);
  assert.match(runnerMarketplaceSource, /option\.name\.startsWith\(prefix\)/);
  assert.match(runnerMarketplaceSource, /registrationDeadline/);
  assert.match(runnerMarketplaceSource, /sessionStorage\.setItem\(/);
});

test('requires the selected AgentRunner mandatory configuration before finishing', () => {
  assert.match(
    wizardSource,
    /isRequiredRunnerConfigComplete\(selectedRunnerConfigItems, runnerConfig\)/,
  );
  assert.match(
    wizardSource,
    /return selectedRunner !== null && isRunnerConfigComplete/,
  );
  assert.match(
    wizardSource,
    /!selectedRunner \|\|[\s\S]*?!isRunnerConfigComplete \|\|[\s\S]*?!createdBotUuid/,
  );
});

test('requires an observed message only for the message-reply scenario', () => {
  assert.match(
    wizardSource,
    /selectedScenario !== 'message_reply' \|\| messageReceived/,
  );
  assert.match(
    wizardSource,
    /requiresMessageVerification=\{selectedScenario === 'message_reply'\}/,
  );
  assert.match(wizardSource, /onMessageReceived=\{handleMessageReceived\}/);
});

test('warns local-account users after the bot receives an IM message', () => {
  assert.match(
    wizardSource,
    /messageReceived && userInfo\?\.account_type !== 'space'/,
  );
  assert.match(
    wizardSource,
    /wizard\.botConfig\.messageReceivedLocalAccountWarning/,
  );
  assert.match(wizardSource, /<AlertTriangle className="size-3 text-white"/);
});

test('offers the HTTP Bot test through the signed inbound API', () => {
  assert.match(
    wizardSource,
    /testHttpBotInbound\(createdBotUuid, testMessage\.trim\(\)\)/,
  );
  assert.match(wizardSource, /wizard\.botConfig\.sendHttpTest/);
});

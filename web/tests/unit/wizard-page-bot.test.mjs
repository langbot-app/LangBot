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

test('keeps the 4.11 AgentRunner marketplace installation flow', () => {
  assert.match(wizardSource, /RUNNER_COMPONENT_FILTER = 'AgentRunner'/);
  assert.match(wizardSource, /installPluginFromMarketplace\(/);
  assert.match(wizardSource, /runnerPluginPrefix\(plugin\)/);
  assert.match(wizardSource, /registrationDeadline/);
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

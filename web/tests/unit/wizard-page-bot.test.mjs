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

test('defaults the AI engine step to the workbench option and lists it first', () => {
  assert.match(
    wizardSource,
    /const \[aiChoice, setAiChoice\] = useState<[\s\S]*?>\('more-features'\);/,
  );

  const choicesStart = wizardSource.indexOf('const choices = [');
  const moreFeaturesChoice = wizardSource.indexOf(
    "id: 'more-features' as const",
    choicesStart,
  );
  const externalChoice = wizardSource.indexOf(
    "id: 'external' as const",
    choicesStart,
  );
  const ownModelChoice = wizardSource.indexOf(
    "id: 'own-model' as const",
    choicesStart,
  );

  assert.ok(choicesStart >= 0);
  assert.ok(moreFeaturesChoice > choicesStart);
  assert.ok(moreFeaturesChoice < externalChoice);
  assert.ok(moreFeaturesChoice < ownModelChoice);
});

test('uses the external-runner layout only while that configuration is open', () => {
  assert.match(
    wizardSource,
    /currentStep === 2 && aiChoice === 'external' && selectedRunner/,
  );
});

test('restores the default workbench choice when leaving a nested AI setup', () => {
  assert.equal(
    wizardSource.match(/onChoiceChange\('more-features'\)/g)?.length,
    3,
  );
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

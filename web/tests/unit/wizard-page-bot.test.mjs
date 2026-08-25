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

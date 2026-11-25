import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/utils/coreVersion.ts',
);

function loadCoreVersion() {
  const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('module', 'exports', compiled)(
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports;
}

const { isCoreUpdate, coreReleaseOf, parseCoreVersion } = loadCoreVersion();
const FEED = ['4.11.8', '4.11.7', '4.11.5', '4.11.0'];
const pending = (current) => FEED.filter((v) => isCoreUpdate(v, current));

test('offers newer stable releases to stable installs', () => {
  assert.deepEqual(pending('v4.11.5'), ['4.11.8', '4.11.7']);
  assert.deepEqual(pending('v4.11.8'), []);
  assert.deepEqual(pending('v4.12.0'), []);
  assert.equal(isCoreUpdate('5.0.0', 'v4.11.8'), true);
});

test('a stable release supersedes its own pre-releases (PEP 440 and semver)', () => {
  for (const current of [
    'v4.11.8b1',
    'v4.11.8rc2',
    'v4.11.8a1',
    'v4.11.8.dev0',
    'v4.11.8-beta.1',
    'v4.11.8.beta1',
  ]) {
    assert.deepEqual(pending(current), ['4.11.8'], current);
  }
  assert.deepEqual(pending('v4.11.0rc1'), FEED);
});

test('pre-releases ahead of the latest stable get no prompt', () => {
  assert.deepEqual(pending('v4.12.0b1'), []);
  assert.deepEqual(pending('v4.12.0.dev0'), []);
  assert.equal(coreReleaseOf('v4.12.0b1'), null);
});

test('post releases and local builds count as their base release', () => {
  for (const current of ['v4.11.8.post1', 'v4.11.8+custom', 'v4.11.8-post2']) {
    assert.deepEqual(pending(current), [], current);
    assert.equal(coreReleaseOf(current), '4.11.8', current);
  }
  assert.deepEqual(pending('v4.11.5+mybuild'), ['4.11.8', '4.11.7']);
});

test('unparseable versions never prompt an update', () => {
  for (const current of ['vcustom', 'v4.11', '', null, undefined, 'latest']) {
    assert.equal(parseCoreVersion(current), null, String(current));
    assert.deepEqual(pending(current), [], String(current));
  }
});

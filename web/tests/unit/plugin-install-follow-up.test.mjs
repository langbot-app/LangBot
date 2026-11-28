import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/home/plugins/components/plugin-install-task/plugin-follow-up.ts',
);
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const sourceRequire = createRequire(sourcePath);
const loadedModule = { exports: {} };
new Function('require', 'module', 'exports', compiled)(
  sourceRequire,
  loadedModule,
  loadedModule.exports,
);

const { followUpKindsForPlugin } = loadedModule.exports;

const pluginWith = (...kinds) => ({
  components: kinds.map((kind) => ({ manifest: { manifest: { kind } } })),
});

test('Runner asks for an agent or plugin processor', () => {
  assert.deepEqual(followUpKindsForPlugin(pluginWith('Runner')), ['agents']);
});

test('KnowledgeEngine asks for a knowledge base', () => {
  assert.deepEqual(followUpKindsForPlugin(pluginWith('KnowledgeEngine')), [
    'knowledge',
  ]);
});

test('EventListener and Command ask for a bot; Tool asks for a pipeline', () => {
  for (const kind of ['EventListener', 'Command']) {
    assert.deepEqual(followUpKindsForPlugin(pluginWith(kind)), ['bots']);
  }
  assert.deepEqual(followUpKindsForPlugin(pluginWith('Tool')), ['pipelines']);
});

test('the bot step is shown once for any mix of its component kinds', () => {
  assert.deepEqual(
    followUpKindsForPlugin(pluginWith('Tool', 'Command', 'EventListener')),
    ['bots', 'pipelines'],
  );
  assert.deepEqual(
    followUpKindsForPlugin(pluginWith('EventListener', 'Command')),
    ['bots'],
  );
});

test('multi-component plugins keep every distinct follow-up', () => {
  assert.deepEqual(
    followUpKindsForPlugin(
      pluginWith('Runner', 'Tool', 'Command', 'KnowledgeEngine'),
    ),
    ['agents', 'bots', 'pipelines', 'knowledge'],
  );
  assert.deepEqual(
    followUpKindsForPlugin(pluginWith('KnowledgeEngine', 'Command')),
    ['bots', 'knowledge'],
  );
});

test('the order is stable regardless of manifest order', () => {
  assert.deepEqual(
    followUpKindsForPlugin(
      pluginWith('KnowledgeEngine', 'Command', 'Runner', 'Tool'),
    ),
    followUpKindsForPlugin(
      pluginWith('Runner', 'Tool', 'Command', 'KnowledgeEngine'),
    ),
  );
});

test('component kinds without a follow-up do not add a step', () => {
  assert.deepEqual(followUpKindsForPlugin(pluginWith('Parser', 'Page')), []);
  assert.deepEqual(
    followUpKindsForPlugin(
      pluginWith('Parser', 'Tool', 'Page', 'KnowledgeRetriever'),
    ),
    ['pipelines'],
  );
});

test('a missing plugin or component list yields no follow-up', () => {
  for (const plugin of [null, undefined, {}, { components: null }]) {
    assert.deepEqual(followUpKindsForPlugin(plugin), []);
  }
  assert.deepEqual(
    followUpKindsForPlugin({ components: [{}, { manifest: null }] }),
    [],
  );
});

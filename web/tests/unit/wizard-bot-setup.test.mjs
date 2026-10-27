import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
function load(path, deps = {}) {
  const mod = { exports: {} };
  new Function(
    'require',
    'exports',
    ts.transpileModule(
      fs.readFileSync(new URL('../../src/' + path, import.meta.url), 'utf8'),
      { compilerOptions: { module: ts.ModuleKind.CommonJS } },
    ).outputText,
  )((id) => deps[id], mod.exports);
  return mod.exports;
}
const template = load(
  'app/home/bots/components/bot-form/message-routing-template.ts',
);
const { prepareWizardBot, wizardBindingsIfMissing } = load(
  'app/wizard/bot-setup.ts',
  { '@/app/home/bots/components/bot-form/message-routing-template': template },
);
const bot = {
  name: 'Wizard QA',
  description: '',
  adapter: 'onebot',
  adapter_config: {},
  enable: false,
};
test('fresh wizard binds both rules to its own pipeline and back navigation reuses the bot', async () => {
  const calls = [];
  let saved;
  const client = {
    createPipeline: async (p) => {
      calls.push('pipeline');
      assert.deepEqual(p.config, {});
      return { uuid: 'p' };
    },
    createBot: async (b) => {
      calls.push('bot');
      saved = b;
      return { uuid: 'b' };
    },
    getBot: async () => ({ bot: saved }),
  };
  const draft = { adapter: 'onebot', botUuid: null, pipelineUuid: null };
  await prepareWizardBot(client, draft, bot, 'QA pipeline');
  assert.deepEqual(calls, ['pipeline', 'bot']);
  assert.equal(saved.event_bindings.length, 2);
  assert.ok(saved.event_bindings.every((b) => b.target_uuid === 'p'));
  assert.deepEqual(saved.event_bindings[1].filters[1], {
    field: 'is_at_bot',
    operator: 'eq',
    value: true,
  });
  saved.adapter_config = { token: 'edited' };
  assert.equal(
    (await prepareWizardBot(client, draft, bot, 'QA pipeline')).bot
      .adapter_config.token,
    'edited',
  );
  assert.deepEqual(calls, ['pipeline', 'bot']);
});
test('retry after bot failure reuses the successful pipeline', async () => {
  let pipelines = 0,
    bots = 0;
  const client = {
    createPipeline: async () => ({ uuid: 'p' + ++pipelines }),
    createBot: async () => {
      if (++bots === 1) throw new Error('temporary failure');
      return { uuid: 'b' };
    },
  };
  const draft = { adapter: 'onebot', botUuid: null, pipelineUuid: null };
  await assert.rejects(prepareWizardBot(client, draft, bot, 'p'));
  await prepareWizardBot(client, draft, bot, 'p');
  assert.equal(pipelines, 1);
  assert.equal(bots, 2);
});
test('existing pipeline rules preserve disabled flags, filters and manual destinations', () => {
  const custom = {
    ...bot,
    event_bindings: [
      {
        id: 'manual',
        event_pattern: '*',
        target_type: 'pipeline',
        target_uuid: 'existing',
        filters: [],
        enabled: false,
      },
    ],
  };
  const before = structuredClone(custom);
  assert.deepEqual(wizardBindingsIfMissing(custom, 'new'), {});
  assert.deepEqual(custom, before);
  const patch = wizardBindingsIfMissing(bot, 'p');
  assert.equal(patch.event_bindings.length, 2);
  assert.deepEqual(wizardBindingsIfMissing({ ...bot, ...patch }, 'p'), {});
});

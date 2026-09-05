import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/agents/components/debug-event-data.ts',
    import.meta.url,
  ),
  'utf8',
);
const module = { exports: {} };
new Function(
  'exports',
  ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText,
)(module.exports);
const {
  createDebugEventData,
  parseDebugEventData,
  debugEventInputText,
  invalidDebugEventField,
} = module.exports;
const samples = { user: '测试用户', message: '你好', feedback: '很有帮助' };

test('message text and common fields belong to the same event data', () => {
  const data = createDebugEventData('message.received', samples);
  data.text = 'A different message';
  data.user_name = 'Alice';
  data.custom = { nested: true };
  const restored = parseDebugEventData(JSON.stringify(data));
  assert.deepEqual(restored, data);
  assert.equal(
    debugEventInputText('message.received', restored),
    'A different message',
  );
  assert.equal(restored.user_name, 'Alice');
  assert.equal(createDebugEventData('message.received', samples).text, '你好');
});

test('non-message events and deleted messages do not require fabricated conversation text', () => {
  for (const event of [
    'group.member_left',
    'friend.request_received',
    'message.deleted',
    'message.reaction',
  ]) {
    const data = createDebugEventData(event, samples);
    assert.equal(invalidDebugEventField(event, data), undefined);
    assert.equal(debugEventInputText(event, data), '');
    assert.equal(data.text, undefined);
  }
});

test('edited message uses the edited content, not an event description', () => {
  const data = createDebugEventData('message.edited', samples);
  data.text = 'Corrected message';
  assert.equal(
    debugEventInputText('message.edited', data),
    'Corrected message',
  );
  assert.equal(
    invalidDebugEventField('message.edited', { ...data, text: '  ' }).key,
    'text',
  );
});

test('invalid JSON cannot silently become an empty event', () => {
  for (const text of ['', '{', 'null', '[]', '"hello"', '12']) {
    assert.equal(parseDebugEventData(text), null);
  }
  const data = { arbitrary: { list: [1, true] } };
  assert.deepEqual(parseDebugEventData(JSON.stringify(data)), data);
  assert.equal(invalidDebugEventField('custom.example', data), undefined);
  assert.equal(invalidDebugEventField('constructor', data), undefined);
});

test('duration and rating remain numbers and reject invalid values', () => {
  const data = createDebugEventData('bot.muted', samples);
  assert.equal(data.duration, 60);
  for (const duration of [-1, 0.5, '60']) {
    assert.equal(
      invalidDebugEventField('bot.muted', { ...data, duration }).key,
      'duration',
    );
  }
  assert.equal(
    invalidDebugEventField('bot.muted', { ...data, duration: 0 }),
    undefined,
  );
  assert.equal(
    invalidDebugEventField('feedback.received', { rating: 6 }).key,
    'rating',
  );
});

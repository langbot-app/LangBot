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

test('processor common fields edit nested SDK data without losing JSON-only fields', () => {
  const { setDebugEventField, getDebugEventField } = module.exports;
  const data = createDebugEventData('group.member_joined', samples, true);
  assert.deepEqual(data, {
    member: { nickname: '测试用户', id: 'debug-user' },
    group: { id: 'debug-group' },
  });
  data.member.username = 'alice';
  data.inviter = { id: 'inviter-1' };
  const edited = setDebugEventField(data, 'member.id', 'member-42');
  assert.equal(edited.member.id, 'member-42');
  assert.equal(edited.member.username, 'alice');
  assert.deepEqual(edited.inviter, data.inviter);
  assert.equal(data.member.id, 'debug-user');
  assert.equal(getDebugEventField(edited, 'member.id'), 'member-42');
  assert.equal(
    invalidDebugEventField('group.member_joined', edited, true),
    undefined,
  );
});

test('processor message content uses SDK message chains and feedback uses SDK fields', () => {
  const { setDebugEventField, processorDebugEventTypes } = module.exports;
  for (const [type, field] of [
    ['message.received', 'message_chain'],
    ['message.edited', 'new_content'],
  ]) {
    const data = createDebugEventData(type, samples, true);
    const edited = setDebugEventField(data, `${field}.0.text`, 'Changed');
    assert.deepEqual(edited[field], [{ type: 'Plain', text: 'Changed' }]);
    assert.equal(debugEventInputText(type, edited, true), 'Changed');
    assert.equal(data[field][0].text, '你好');
  }
  const feedback = createDebugEventData('feedback.received', samples, true);
  assert.equal(feedback.feedback_type, 1);
  assert.equal(feedback.feedback_content, '很有帮助');
  assert.ok(feedback.feedback_id);
  for (const type of processorDebugEventTypes) {
    assert.equal(
      invalidDebugEventField(
        type,
        createDebugEventData(type, samples, true),
        true,
      ),
      undefined,
      type,
    );
  }
});

test('processor full JSON accepts rich messages without requiring a first text component', () => {
  const data = createDebugEventData('message.received', samples, true);
  data.message_chain = [
    { type: 'Image', url: 'https://example.com/image.png' },
  ];
  assert.equal(
    invalidDebugEventField('message.received', data, true),
    undefined,
  );
});

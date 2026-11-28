import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/home/bots/components/bot-session/session-scope.ts',
);

function loadHelpers() {
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

const { parseGroupMemberSessionId, parseSessionType, sessionGroupId } =
  loadHelpers();

// Expected values come from build_monitoring_session_id/parse_group_member_id
// in src/langbot/pkg/persistence/session_summary_contract.py.
test('decodes per-member IDs exactly like the backend', () => {
  assert.deepEqual(parseGroupMemberSessionId('groupmember_6_team_a_b'), {
    groupId: 'team_a',
    memberId: 'b',
  });
  assert.deepEqual(parseGroupMemberSessionId('groupmember_4_team_a_b'), {
    groupId: 'team',
    memberId: 'a_b',
  });
  assert.deepEqual(parseGroupMemberSessionId('groupmember_4_群聊_1_用户:42'), {
    groupId: '群聊_1',
    memberId: '用户:42',
  });
});

test('rejects malformed per-member IDs instead of guessing', () => {
  for (const id of [
    'groupmember_06_team_a_b',
    'groupmember_6_team_a_',
    'groupmember_x_a_b',
    'groupmember_9_ab_c',
    'groupmember_1_a_ b',
    'group_team_a_b',
  ]) {
    assert.equal(parseGroupMemberSessionId(id), null, id);
  }
});

test('classifies session types by prefix first', () => {
  assert.equal(parseSessionType('groupmember_9_person123_u'), 'group');
  assert.equal(parseSessionType('person_group1'), 'person');
  assert.equal(parseSessionType('group_1'), 'group');
  assert.equal(parseSessionType('bot.PERSON_42'), 'person');
  assert.equal(parseSessionType('websocket-session'), null);
});

test('finds the group of per-member and whole-group sessions', () => {
  assert.equal(sessionGroupId('groupmember_6_team_a_b'), 'team_a');
  assert.equal(sessionGroupId('group_team_a'), 'team_a');
  assert.equal(sessionGroupId('group_team_a#topic'), null);
  assert.equal(sessionGroupId('person_team_a'), null);
});

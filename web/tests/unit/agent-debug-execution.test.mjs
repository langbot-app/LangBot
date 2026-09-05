import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../../src/app/home/agents/components/debug-execution.ts', import.meta.url), 'utf8');
const module = { exports: {} };
new Function('exports', ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText)(module.exports);
const { executionSteps } = module.exports;
const event = (type, data) => ({type, data});
test('separates streamed thinking and text, replaces final snapshot without duplication', () => {
  assert.deepEqual(executionSteps([
    event('message.delta', {chunk: {content:'<think>plan'}}),
    event('message.delta', {chunk: {content:'</think>hello'}}),
    event('message.completed', {message: {content:'<think>plan</think>hello'}}),
    event('run.completed', {message: {content:'hello'}}),
  ]), [{kind:'message', text:'hello', reasoning:'plan'}]);
});
test('retains structured reasoning and tool parameters/results in order', () => {
  const steps = executionSteps([
    event('message.delta', {chunk: {provider_specific_fields:{reasoning_content:'plan'}}}),
    event('message.completed', {message: {content:''}}),
    event('tool.call.started', {tool_call_id:'1',tool_name:'exec', parameters:{command:'echo hi'}}),
    event('tool.call.started', {tool_call_id:'2',tool_name:'exec', parameters:{command:'bad'}}),
    event('tool.call.completed', {tool_call_id:'2',tool_name:'exec', error:'failed'}),
    event('tool.call.completed', {tool_call_id:'1',tool_name:'exec', result:{stdout:'hi'}}),
    event('run.failed', {}),
  ]);
  assert.equal(steps[0].reasoning, 'plan');
  assert.equal(steps[1].parameters.command, 'echo hi');
  assert.deepEqual(steps[1].result, {stdout:'hi'});
  assert.equal(steps[2].status, 'failed');
  assert.equal(steps[2].error, 'failed');
});

test('replaces LocalAgent cumulative snapshots instead of repeating text', () => {
  assert.deepEqual(executionSteps([
    event('message.delta', {chunk: {content:'hello', msg_sequence:1}}),
    event('message.delta', {chunk: {content:'hello world', msg_sequence:2}}),
    event('message.delta', {chunk: {content:'hello world', msg_sequence:3, is_final:true}}),
  ]), [{kind:'message', text:'hello world', reasoning:''}]);
});

test('shows failed tool results even when the call transport completed', () => {
  const steps = executionSteps([
    event('tool.call.started', {tool_call_id:'exit7', tool_name:'exec', parameters:{command:'exit 7'}}),
    event('tool.call.completed', {tool_call_id:'exit7', tool_name:'exec', result:{ok:false, exit_code:7, stderr:'expected'}}),
  ]);
  assert.equal(steps[0].status,'failed');
  assert.equal(steps[0].result.exit_code,7);
});

test('does not repeat prior thinking across LocalAgent tool turns', () => {
  const prefix = '<think>first thought</think>';
  const steps = executionSteps([
    event('message.delta', {chunk:{content:prefix, msg_sequence:1}}),
    event('tool.call.started', {tool_call_id:'w',tool_name:'write',parameters:{path:'/workspace/a'}}),
    event('tool.call.completed', {tool_call_id:'w',tool_name:'write',result:{ok:true}}),
    event('message.delta', {chunk:{content:prefix+'now read',msg_sequence:1}}),
    event('tool.call.started', {tool_call_id:'r',tool_name:'read'}),
    event('tool.call.completed', {tool_call_id:'r',tool_name:'read',result:{ok:true}}),
    event('message.delta', {chunk:{content:prefix+'now read'+'done',msg_sequence:1}}),
    event('message.completed', {message:{content:'done'}}),
  ]);
  const messages = steps.filter(s=>s.kind==='message');
  assert.deepEqual(messages, [
    {kind:'message',text:'',reasoning:'first thought'},
    {kind:'message',text:'now read',reasoning:''},
    {kind:'message',text:'done',reasoning:''},
  ]);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(testDir, '../..');

function readSource(relativePath) {
  return fs.readFileSync(path.join(webRoot, relativePath), 'utf8');
}

test('agent and pipeline details share the split processor workbench', () => {
  const workbench = readSource(
    'src/app/home/components/processor-detail/ProcessorDetailWorkbench.tsx',
  );
  const agentDetail = readSource('src/app/home/agents/AgentDetailContent.tsx');
  const pipelineDetail = readSource(
    'src/app/home/pipelines/PipelineDetailContent.tsx',
  );
  const websocketClient = readSource(
    'src/app/infra/websocket/WebSocketClient.ts',
  );
  const pipelineDebug = readSource(
    'src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx',
  );

  assert.match(
    workbench,
    /lg:grid-cols-\[minmax\(20rem,0\.72fr\)_minmax\(0,1\.28fr\)\]/,
  );
  assert.ok(
    workbench.indexOf('{debugContent}') < workbench.indexOf('{configContent}'),
  );
  assert.match(agentDetail, /<ProcessorDetailWorkbench/);
  assert.match(agentDetail, /debugContent=/);
  assert.match(pipelineDetail, /<ProcessorDetailWorkbench/);
  assert.match(pipelineDetail, /compact=\{true\}/);
  assert.doesNotMatch(
    websocketClient,
    /this\.ws\.onopen = \(\) => \{\s*this\.reconnectAttempts = 0/,
  );
  assert.match(
    websocketClient,
    /data\.type === 'connected'[\s\S]*this\.reconnectAttempts = 0/,
  );
  assert.match(pipelineDebug, /data-slot="scroll-area-viewport"/);
  assert.doesNotMatch(pipelineDebug, /scrollIntoView/);
});

test('processor forms expose their primary orchestration flow horizontally', () => {
  const agentForm = readSource(
    'src/app/home/agents/components/AgentFormComponent.tsx',
  );
  const pipelineForm = readSource(
    'src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx',
  );

  assert.match(
    agentForm,
    /name: 'basic'[\s\S]*name: 'events'[\s\S]*name: 'runner'[\s\S]*name: 'runner_config'/,
  );
  assert.match(
    pipelineForm,
    /const primarySectionNames = \['trigger', 'ai', 'output'\]/,
  );
  assert.match(agentForm, /<TabsList[^>]*grid-cols-4/);
  assert.match(pipelineForm, /<TabsList[^>]*grid-cols-3/);
  assert.doesNotMatch(agentForm, /<ol className=/);
  assert.doesNotMatch(pipelineForm, /<ol className=/);
});

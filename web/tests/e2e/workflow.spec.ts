import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('processors offer workflow creation and open the workflow editor', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  let createdName = '';
  await page.route('**/api/v1/workflows**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = { workflows: [] };
    if (route.request().method() === 'POST') {
      createdName = route.request().postDataJSON().name;
      data = { uuid: 'created-workflow' };
    } else if (path.endsWith('/created-workflow')) {
      data = {
        workflow: {
          uuid: 'created-workflow',
          name: createdName,
          nodes: [],
          edges: [],
          settings: {},
          variables: {},
          is_enabled: true,
        },
      };
    } else if (path.endsWith('/_/node-types')) {
      data = { node_types: [], categories: [] };
    }
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.goto('/home/agents?id=new');
  await page.locator('[data-processor-kind="workflow"]').click();
  await page.locator('input[name="name"]').fill('Created workflow');
  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  await expect(page).toHaveURL(/\/home\/workflows\?id=created-workflow/);
  expect(createdName).toBe('Created workflow');
  await expect(page.getByRole('tab', { name: 'Test run' })).toBeVisible();
});

test('workflow test run shows replies and persisted node details', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const workflow = {
    uuid: 'workflow-1',
    name: 'Echo workflow',
    description: '',
    version: 1,
    is_enabled: true,
    nodes: [],
    edges: [],
    variables: {},
    settings: {},
  };
  const execution = {
    uuid: 'execution-1',
    workflow_uuid: workflow.uuid,
    status: 'completed',
    node_executions: [
      {
        node_id: 'trigger',
        node_type: 'message_trigger',
        status: 'completed',
        inputs: {},
        outputs: { message: 'hello' },
      },
      {
        node_id: 'condition',
        node_type: 'condition',
        status: 'completed',
        inputs: { input: 'hello' },
        outputs: { true: 'hello' },
      },
      {
        node_id: 'reply',
        node_type: 'reply_message',
        status: 'completed',
        inputs: { input: 'hello' },
        outputs: { message_content: 'Echo hello' },
      },
    ],
  };
  let runInput: unknown;
  await page.route('**/api/v1/workflows**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path.endsWith('/run')) {
      runInput = route.request().postDataJSON();
      data = {
        execution_uuid: execution.uuid,
        status: 'completed',
        replies: ['Echo hello'],
      };
    } else if (path.endsWith('/_/node-types'))
      data = { node_types: [], categories: [] };
    else if (path.endsWith('/executions/execution-1')) data = { execution };
    else if (path.endsWith('/executions'))
      data = { executions: [execution], total: 1 };
    else if (path.endsWith('/workflow-1')) data = { workflow };
    else data = { workflows: [workflow] };
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.goto('/home/workflows?id=workflow-1');
  await page.getByRole('tab', { name: 'Test run' }).click();
  await page.getByRole('textbox', { name: 'Message input' }).fill('hello');
  await page.getByRole('button', { name: 'Test run', exact: true }).click();
  await expect(page.getByText('Echo hello', { exact: true })).toBeVisible();
  await expect(page.getByText('execution-1: completed')).toBeVisible();
  await expect(page.locator('summary')).toHaveCount(3);
  expect(runInput).toEqual({ message: 'hello', session_type: 'person' });
  await page.screenshot({
    path: testInfo.outputPath('workflow-test-run.png'),
    fullPage: true,
  });
  await page.getByRole('tab', { name: /Execution/ }).click();
  await page.getByRole('button', { name: /execution-1.*completed/ }).click();
  await expect(page.locator('summary')).toHaveCount(3);
});

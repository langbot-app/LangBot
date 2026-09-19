import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
const contract = JSON.parse(
  readFileSync('tests/e2e/fixtures/runner-migration-contract.json', 'utf8'),
);
import { installLangBotApiMocks } from './fixtures/langbot-api';
const canonical = contract.cases[0].plan.config;
const outputSchema = contract.output_schema;
const switchField = (page: Page, label: string) =>
  page
    .locator('label')
    .filter({ hasText: label })
    .locator('../..')
    .getByRole('switch');
async function setup(
  page: Page,
  plugin = 'weknora-agent',
  name = 'WeKnoraAgent',
  agentId: null | 'absent' = null,
  converted?: typeof canonical,
) {
  const schema = contract.plugins[plugin].component;
  const id = `plugin:langbot-team/${name}/default`;
  const raw: Record<string, unknown> = {
    'api-key': '  fixture credential  ',
    'base-url': '  http://localhost:8080/api/v1  ',
    'app-type': 'agent',
    'enable-all-tools': false,
    tools: ['tool-allowed'],
    'knowledge-bases': ['kb-allowed'],
    'mcp-resources': [{ server: 'private', uri: 'secret' }],
    'mcp-resource-agent-read-enabled': false,
  };
  if (agentId === null) raw['agent-id'] = null;
  if (plugin === 'LocalAgent') {
    raw['advanced-settings'] = true;
    raw.model = {
      primary: 'llm-valid',
      fallbacks: [],
      reasoning: { 'llm-valid': 'provider_default' },
    };
    raw['remove-think'] = true;
  }
  let config = {
    ...structuredClone(canonical),
    ai: { runner: { id }, runner_config: { [id]: raw } },
  };
  if (converted) config = structuredClone(converted);
  else config.output.misc['remove-think'] = false; // Deliberate disagreement must not synchronize on mount.
  const writes: any[] = [];
  await installLangBotApiMocks(page, { authenticated: true });
  await page.routeWebSocket('**/api/v1/pipelines/**/ws/connect**', (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type === 'authenticate')
        ws.send(
          JSON.stringify({
            type: 'connected',
            connection_id: 'fixture',
            session_type: 'person',
          }),
        );
    });
  });
  await page.route('**/api/v1/pipelines/preserve', async (route) => {
    if (route.request().method() !== 'GET') {
      const body = route.request().postDataJSON();
      writes.push(body);
      if (body.config) config = body.config;
    }
    await route.fulfill({
      json: {
        code: 0,
        data: {
          pipeline: {
            uuid: 'preserve',
            name: 'Preservation',
            description: '',
            emoji: '⚙️',
            config,
          },
        },
      },
    });
  });
  await page.route('**/api/v1/pipelines/_/metadata', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          configs: [
            {
              name: 'ai',
              label: { en_US: 'AI' },
              stages: [
                {
                  name: 'runner',
                  label: { en_US: 'Runner' },
                  config: contract.ai_schema.stages[0].config.map(
                    (field: Record<string, unknown>) =>
                      field.name === 'id'
                        ? {
                            ...field,
                            default: id,
                            options: [
                              { name: id, label: schema.metadata.label },
                            ],
                          }
                        : field,
                  ),
                },
                {
                  name: id,
                  label: schema.metadata.label,
                  config: schema.spec.config,
                },
              ],
            },
            outputSchema,
          ],
        },
      },
    }),
  );
  await page.goto('/home/pipelines?id=preserve');
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  return { writes, raw, id };
}

for (const kind of ['json', 'prompt', 'prompt-omitted'] as const) {
  test(`canonical ${kind} edits preserve types and metadata, reject invalid drafts`, async ({
    page,
  }) => {
    const candidate = contract.cases.find(
      (c: any) =>
        c.legacy_runner === (kind === 'json' ? 'langflow-api' : 'local-agent'),
    );
    const config = structuredClone(candidate.plan.config);
    const id = candidate.plan.target_runner_id;
    const field = kind === 'json' ? 'tweaks' : 'prompt';
    const initial =
      kind === 'json'
        ? {
            node: {
              enabled: false,
              count: 0,
              missing: null,
              list: [false, 0, null],
            },
          }
        : kind === 'prompt-omitted'
          ? [
              {
                role: 'assistant',
                tool_calls: [],
                name: 'original',
                provider_specific_fields: { cache: false, count: 0 },
              },
            ]
          : [
              {
                role: 'user',
                content: [{ type: 'text', text: 'original' }],
                name: 'alice',
                metadata: { flag: false, count: 0 },
              },
              {
                role: 'assistant',
                content: null,
                tool_calls: [
                  {
                    id: 'call1',
                    type: 'function',
                    function: { name: 'foo', arguments: '{}' },
                  },
                ],
              },
              { role: 'tool', content: [], tool_call_id: 'call1' },
            ];
    config.ai.runner_config[id][field] = initial;
    config.ai.runner_config[id]['advanced-settings'] = true;
    const { writes } = await setup(
      page,
      kind === 'json' ? 'langflow-agent' : 'LocalAgent',
      candidate.plan.target_plugin.name,
      null,
      config,
    );
    const editor = page.getByTestId(`structured-editor-${field}`);
    await expect(editor).toBeVisible();
    expect(JSON.parse(await editor.inputValue())).toEqual(initial);
    expect(writes).toHaveLength(0);
    await expect(
      page.getByRole('button', { name: 'Save', exact: true }),
    ).toBeDisabled();
    const edited = structuredClone(initial) as any;
    if (kind === 'json') edited.node.count = 7;
    else if (kind === 'prompt-omitted') edited[0].name = 'edited';
    else edited[0].content[0].text = 'edited';
    await editor.fill(JSON.stringify(edited, null, 2));
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0].config.ai.runner_config[id][field]).toEqual(edited);
    if (kind === 'prompt-omitted')
      expect(
        Object.hasOwn(
          writes[0].config.ai.runner_config[id][field][0],
          'content',
        ),
      ).toBe(false);
    await page.reload();
    await page.getByRole('tab', { name: 'AI', exact: true }).click();
    expect(JSON.parse(await editor.inputValue())).toEqual(edited);
    await editor.fill('{ invalid');
    await expect(
      page.getByRole('alert').filter({ hasText: `${field} (JSON)` }),
    ).toBeVisible();
    if (kind === 'json') await switchField(page, 'Advanced Settings').click();
    // Make another valid edit so Save remains available: invalid JSON must
    // block the entire save, not silently persist the previous value.
    await page.getByRole('tab', { name: 'Output', exact: true }).click();
    await switchField(page, 'Quote Origin Message').click();
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.waitForTimeout(400);
    expect(writes).toHaveLength(1);
    await page.getByRole('tab', { name: 'AI', exact: true }).click();
    if (kind === 'json') await switchField(page, 'Advanced Settings').click();
    await expect(editor).toHaveValue('{ invalid');
    await editor.fill(JSON.stringify(edited));
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect.poll(() => writes.length).toBe(2);
    expect(writes[1].config.ai.runner_config[id][field]).toEqual(edited);
  });
}

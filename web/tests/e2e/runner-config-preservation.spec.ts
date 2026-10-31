import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
const contract = JSON.parse(
  readFileSync('tests/e2e/fixtures/runner-migration-contract.json', 'utf8'),
);
import { installLangBotApiMocks } from './fixtures/langbot-api';
const canonical = JSON.parse(
  readFileSync('../src/langbot/templates/default-pipeline-config.json', 'utf8'),
);
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
for (const candidate of contract.cases) {
  test(`actual converter output stays editable and unchanged for ${candidate.legacy_runner}`, async ({
    page,
  }) => {
    const name = candidate.plan.target_plugin.name;
    const folder = Object.keys(contract.plugins).find(
      (key) => contract.plugins[key].manifest.metadata.name === name,
    )!;
    const { writes } = await setup(
      page,
      folder,
      name,
      null,
      candidate.plan.config,
    );
    await expect(
      page.getByRole('button', { name: 'Save', exact: true }),
    ).toBeDisabled();
    expect(writes).toHaveLength(0);
    await page.getByRole('tab', { name: 'Output', exact: true }).click();
    await switchField(page, 'Quote Origin Message').click();
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0].config.ai).toEqual(candidate.plan.config.ai);
    expect(writes[0].config.output.misc['quote-origin']).toBe(
      !candidate.plan.config.output.misc['quote-origin'],
    );
  });
}

for (const agentId of [null, 'absent'] as const) {
  test(`mounted real WeKnora schema preserves ${agentId} agent ID and hidden policy`, async ({
    page,
  }) => {
    const { writes, raw, id } = await setup(
      page,
      'weknora-agent',
      'WeKnoraAgent',
      agentId,
    );
    await expect(page.getByText('Agent ID', { exact: true })).toBeVisible();
    expect(writes).toEqual([]);
    await expect(
      page.getByRole('button', { name: 'Save', exact: true }),
    ).toBeDisabled();
    await switchField(page, 'Enable Web Search').click();
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0].config.ai.runner_config[id]).toEqual({
      ...raw,
      'web-search-enabled': true,
    });
    await page.reload();
    await page.getByRole('tab', { name: 'AI', exact: true }).click();
    await expect(switchField(page, 'Enable Web Search')).toBeChecked();
    await expect(
      page.getByRole('button', { name: 'Save', exact: true }),
    ).toBeDisabled();
    expect(writes).toHaveLength(1);
  });
}
test('remove-think is synchronized only after intentional output or runner toggles', async ({
  page,
}) => {
  const { writes, id } = await setup(page, 'LocalAgent', 'LocalAgent');
  const runnerThink = switchField(page, 'Remove');
  await expect(runnerThink).toBeChecked();
  expect(writes).toEqual([]);
  await page.getByRole('tab', { name: 'Output', exact: true }).click();
  const outputThink = switchField(page, 'Remove CoT');
  await expect(outputThink).not.toBeChecked();
  await outputThink.click();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].config.output.misc['remove-think']).toBe(true);
  expect(writes[0].config.ai.runner_config[id]['remove-think']).toBe(true);
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  await runnerThink.click();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes[1].config.output.misc['remove-think']).toBe(false);
  expect(writes[1].config.ai.runner_config[id]['remove-think']).toBe(false);
});

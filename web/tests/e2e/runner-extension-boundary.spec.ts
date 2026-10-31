import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  pipelineMetadata,
} from './fixtures/langbot-api';

test('independent Runner guidance remains visible with extensions disabled', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/pipelines/*/extensions', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          enable_all_plugins: false,
          enable_all_mcp_servers: false,
          enable_all_skills: false,
          bound_plugins: [],
          available_plugins: [],
          bound_mcp_servers: [],
          available_mcp_servers: [],
          bound_skills: [],
          available_skills: [],
        },
      },
    }),
  );
  await page.goto('/home/pipelines?id=boundary');
  await page.locator('[data-guide="pipeline-section-ai"]').click();
  await expect(
    page.getByText(
      'Select the Runner independently here, regardless of extension plugin switches. Its plugin must still be installed and available.',
    ),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await expect(
    page.getByText(
      'Only controls event listeners, tools and commands for this pipeline; does not affect the Runner selected in AI settings.',
    ),
  ).toBeVisible();
});

for (const problem of ['missing', 'disabled', 'runtime'] as const) {
  test(`Runner ${problem} diagnosis keeps the draft and opens repair separately`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const id = 'plugin:langbot-team/LocalAgent/default';
    const config = {
      ai: { runner: { id }, runner_config: { [id]: { hidden: null } } },
    };
    const writes: unknown[] = [];
    await page.route('**/api/v1/pipelines/diagnosis', async (route) => {
      if (route.request().method() === 'PUT')
        writes.push(route.request().postDataJSON());
      await route.fulfill({
        json: {
          code: 0,
          data: {
            pipeline: {
              uuid: 'diagnosis',
              name: 'Diagnosis',
              description: '',
              emoji: '⚙️',
              config,
            },
          },
        },
      });
    });
    await page.route('**/api/v1/system/status/plugin-system', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: {
            is_enable: true,
            is_connected: problem !== 'runtime',
            plugin_connector_error: '',
          },
        },
      }),
    );
    await page.route('**/api/v1/plugins', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: {
            plugins:
              problem === 'missing'
                ? []
                : [
                    {
                      enabled: problem !== 'disabled',
                      manifest: {
                        manifest: {
                          metadata: {
                            author: 'langbot-team',
                            name: 'LocalAgent',
                          },
                        },
                      },
                    },
                  ],
          },
        },
      }),
    );
    const originalMetadata = pipelineMetadata();
    const metadata = {
      configs: originalMetadata.configs.map((tab) => ({
        ...tab,
        stages: tab.stages.map((stage) => ({
          ...stage,
          config:
            stage.name === id
              ? [
                  {
                    name: 'draft',
                    type: 'string',
                    label: { en_US: 'Draft marker', zh_Hans: '草稿标记' },
                    required: false,
                    default: '',
                  },
                ]
              : stage.config.map((field) =>
                  problem === 'missing' && field.name === 'id'
                    ? { ...field, options: [] }
                    : field,
                ),
        })),
      })),
    };
    await page.route('**/api/v1/pipelines/_/metadata', (route) =>
      route.fulfill({ json: { code: 0, data: metadata } }),
    );
    await page.goto('/home/pipelines?id=diagnosis');
    await page.locator('[data-guide="pipeline-section-ai"]').click();
    const draft = page
      .getByRole('region', { name: 'Configuration', exact: true })
      .getByRole('textbox');
    await draft.fill('unsaved diagnosis draft');
    const alert = page
      .getByRole('alert')
      .filter({ hasText: 'Manage plugins and runtime' });
    await expect(alert).toContainText(
      {
        missing: 'The selected Runner or its plugin is missing.',
        disabled: 'The selected Runner plugin is disabled.',
        runtime: 'The Plugin Runtime is unavailable or disabled.',
      }[problem],
    );
    const repair = alert.getByRole('link', {
      name: 'Manage plugins and runtime',
    });
    await expect(repair).toHaveAttribute('target', '_blank');
    const popup = page.waitForEvent('popup');
    await repair.click();
    await (await popup).close();
    await expect(page).toHaveURL(/id=diagnosis/);
    await expect(draft).toHaveValue('unsaved diagnosis draft');
    await expect(
      page.getByRole('button', { name: 'Save', exact: true }),
    ).toBeEnabled();
    expect(writes).toEqual([]);
  });
}

import { expect, Page, test } from '@playwright/test';

import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

async function save(page: Page) {
  const button = page.getByRole('button', { name: /^Save$/ });
  await expect(button).toBeEnabled();
  await button.click();
}

async function submit(page: Page) {
  await page.getByRole('button', { name: /^Submit$/ }).click();
}

async function selectPlaywrightAdapter(page: Page) {
  await page.getByRole('combobox').click();
  await page.getByRole('option', { name: 'Playwright Adapter' }).click();
}

async function confirmDelete(page: Page) {
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^Confirm Delete$/ })
    .click();
}

async function installDelayedFirstSave(page: Page, apiPath: string) {
  const payloads: Record<string, unknown>[] = [];
  let releaseFirstSave = () => {};
  const firstSaveGate = new Promise<void>((resolve) => {
    releaseFirstSave = resolve;
  });

  await page.route(`**${apiPath}`, async (route) => {
    if (route.request().method() !== 'PUT') {
      await route.fallback();
      return;
    }

    payloads.push(
      JSON.parse(route.request().postData() || '{}') as Record<string, unknown>,
    );
    if (payloads.length === 1) {
      await firstSaveGate;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        message: 'ok',
        data: {},
        timestamp: Date.now(),
      }),
    });
  });

  return { payloads, releaseFirstSave };
}

async function forceFormSubmit(page: Page, formSelector: string) {
  await page.locator(formSelector).evaluate((form) => {
    (form as HTMLFormElement).requestSubmit();
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
}

test.describe('frontend CRUD smoke flows', () => {
  test('viewer keeps ordinary bot and pipeline monitoring access', async ({
    page,
  }) => {
    const workspace = makeWorkspaceEntry(
      'workspace-viewer',
      'Viewer Workspace',
      'local',
    );
    await installLangBotApiMocks(page, {
      authenticated: true,
      workspaces: [workspace],
    });

    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Viewer Test Bot');
    await page
      .locator('input[name="description"]')
      .fill('Proves monitoring is ordinary resource visibility.');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();
    await page.locator('input[name="name"]').fill('Viewer Pipeline');
    await page
      .locator('input[name="description"]')
      .fill('Viewer monitoring permission regression.');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/agents\?id=pipeline-1$/);

    workspace.membership.role = 'viewer';
    workspace.permissions = ['member.view', 'resource.view', 'workspace.view'];

    await page.goto('/home/bots?id=bot-1');
    await expect(page.getByRole('tab', { name: 'Logs' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Sessions' })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Save$/ })).toHaveCount(0);
    await page.getByRole('tab', { name: 'Logs' }).click();
    await expect(page.getByText('No logs yet')).toBeVisible();

    await page.goto('/home/agents?id=pipeline-1');
    await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Debug Chat' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /^Save$/ })).toHaveCount(0);

    await page.goto('/home/monitoring');
    await expect(
      page.getByRole('button', { name: 'Refresh Data' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export Data' })).toHaveCount(
      0,
    );
  });

  test('creates, edits, and deletes a bot', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('Support Bot');
    await page
      .locator('input[name="description"]')
      .fill('Answers customer support questions.');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
    await page.reload();
    await expect(
      page.getByRole('heading', { name: 'Support Bot' }),
    ).toBeVisible();
    await expect(page.locator('input[name="name"]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const botInfoDialog = page.getByRole('dialog');
    await expect(botInfoDialog.getByLabel('Icon')).toHaveCount(0);
    await botInfoDialog.getByLabel('Name').fill('Support Bot Updated');
    await botInfoDialog
      .getByLabel('Description')
      .fill('Answers customer support questions with context.');
    await botInfoDialog.getByRole('button', { name: 'Save' }).click();
    await expect(
      page.getByRole('heading', { name: 'Support Bot Updated' }),
    ).toBeVisible();

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/bots$/);
    await expect(page.getByText('Select a bot from the sidebar')).toBeVisible();
  });

  test('creates, edits, and deletes a pipeline', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('Escalation Pipeline');
    await page
      .locator('input[name="description"]')
      .fill('Routes urgent customer issues.');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/agents\?id=pipeline-1$/);
    await page.reload();
    await expect(
      page.getByRole('heading', { name: /Escalation Pipeline/ }),
    ).toBeVisible();
    await expect(page.locator('input[name="basic.name"]')).toHaveCount(0);
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const pipelineInfoDialog = page.getByRole('dialog');
    await pipelineInfoDialog
      .getByLabel('Description')
      .fill('Routes urgent customer issues to operators.');
    await pipelineInfoDialog.getByRole('button', { name: 'Save' }).click();

    await page.getByRole('button', { name: 'Management' }).click();
    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/agents$/);
    await expect(
      page.getByText('Select an Agent or Pipeline from the sidebar'),
    ).toBeVisible();
  });

  test('opens pipeline AI capabilities with malformed model options', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/agents?id=pipeline-ai');

    await expect(
      page.getByRole('heading', { name: /pipeline-ai/ }),
    ).toBeVisible();
    await page.getByRole('tab', { name: /^AI$/ }).click();

    await expect(page.getByText('Runtime')).toBeVisible();
    await expect(
      page.locator('[data-slot="card-title"]').filter({
        hasText: 'Local Agent',
      }),
    ).toBeVisible();
    await expect(
      page.locator('label').filter({
        hasText: 'Model',
      }),
    ).toBeVisible();
    await expect(page.getByText('A <Select.Item')).toHaveCount(0);
    await expect(page.getByText('500')).toHaveCount(0);
  });

  test('creates, edits, and deletes a knowledge base', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/knowledge?id=new');

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('Support Knowledge');
    await page
      .locator('input[name="description"]')
      .fill('Source material for support answers.');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/knowledge\?id=knowledge-1$/);
    await page.reload();
    await expect(
      page.getByRole('heading', { name: /Support Knowledge/ }),
    ).toBeVisible();
    await expect(page.locator('input[name="name"]')).toHaveCount(0);
    const engineSettings = page.locator('[data-slot="card"]').filter({
      has: page.getByText('Engine Settings', { exact: true }),
    });
    await expect(engineSettings.getByRole('combobox')).toBeVisible();

    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const kbInfoDialog = page.getByRole('dialog');
    await kbInfoDialog.getByLabel('Name').fill('Support Knowledge Updated');
    await kbInfoDialog
      .getByLabel('Description')
      .fill('Updated source material for support answers.');
    await kbInfoDialog.getByRole('button', { name: 'Save' }).click();
    await expect(
      page.getByRole('heading', { name: /Support Knowledge Updated/ }),
    ).toBeVisible();

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/knowledge$/);
    await expect(
      page.getByText('Select a knowledge base from the sidebar'),
    ).toBeVisible();
  });

  test('creates, edits, and deletes an MCP server', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/mcp?id=new');

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('playwright-mcp');
    await page
      .locator('input[name="url"]')
      .fill('https://mcp.example.test/sse');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/mcp\?id=playwright-mcp$/);
    await page.reload();
    await expect(page.locator('input[name="name"]')).toHaveValue(
      'playwright-mcp',
    );

    await page
      .locator('input[name="url"]')
      .fill('https://mcp.example.test/updated-sse');
    await save(page);
    await expect(page.locator('input[name="url"]')).toHaveValue(
      'https://mcp.example.test/updated-sse',
    );

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/mcp$/);
    await expect(
      page.getByText('Select an MCP server from the sidebar'),
    ).toBeVisible();
  });

  test('updates and deletes a manually-created skill', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/skills?action=create');

    await page.locator('#display_name').fill('Release Notes');
    await page.locator('#name').fill('release_notes');
    await page.locator('#description').fill('Drafts release notes.');
    await page
      .locator('#instructions')
      .fill('Summarize merged changes for the next release.');
    await save(page);

    await expect(page).toHaveURL(/\/home\/skills\?id=release_notes$/);
    await page.reload();
    await expect(page.locator('#description')).toHaveValue(
      'Drafts release notes.',
    );

    await page
      .locator('#description')
      .fill('Drafts concise release notes for maintainers.');
    await expect(page.locator('#description')).toHaveValue(
      'Drafts concise release notes for maintainers.',
    );
    await save(page);
    await page.reload();
    await expect(page.locator('#description')).toHaveValue(
      'Drafts concise release notes for maintainers.',
    );
    await expect(page.locator('#instructions')).toHaveValue(
      'Summarize merged changes for the next release.',
    );

    await page.getByRole('button', { name: /^Delete$/ }).click();
    await confirmDelete(page);

    await expect(page).toHaveURL(/\/home\/add-extension$/);
  });
});

test.describe('bot advanced flows', () => {
  test('keeps event routing compact and hides raw status errors', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAdapterEvents: true,
    });
    await page.route('**/api/v1/platform/bots/*/event-routes/status', (route) =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ code: -1, msg: 'Internal server error' }),
      }),
    );
    await page.route(
      '**/api/v1/platform/bots/*/event-routes/dry-run',
      (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'ok',
            data: {
              matched: true,
              event_type: 'message.received',
              matched_binding_id: 'binding-1',
              matched_binding_index: 0,
              target: {
                target_type: 'agent',
                target_uuid: 'agent-1',
                target_name: 'NewAgent',
              },
              diagnostic_steps: ['Matched route 1'],
              diagnostic_details: [],
            },
          }),
        }),
    );
    await page.route('**/api/v1/platform/bots/*/event-routes/test', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          msg: 'ok',
          data: {
            dispatched: false,
            event_type: 'message.received',
            failure_code: 'bot_runtime_unavailable',
            reason: 'Bot runtime is unavailable',
            suppressed_outputs: [],
            route_status: {
              routes: [],
              unmatched_events: [],
              stale_routes: [],
            },
          },
        }),
      }),
    );

    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Route Status Bot');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
    await expect(page.getByText('Supported events')).toBeVisible();
    await expect(page.getByText('5 event types')).toBeVisible();
    await expect(page.getByText('Messages · 2')).toBeVisible();
    await expect(page.getByText('Groups · 2')).toBeVisible();
    await expect(page.getByText('Internal server error')).toHaveCount(0);
    await expect(
      page.getByText('Events that match no route are ignored.'),
    ).toHaveCount(0);

    const routingCard = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByText('Event Routing', { exact: true }) });
    const dangerCard = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByText('Danger Zone', { exact: true }) });
    const routingBox = await routingCard.boundingBox();
    const dangerBox = await dangerCard.boundingBox();
    expect(routingBox).not.toBeNull();
    expect(dangerBox).not.toBeNull();
    expect(
      dangerBox!.y - (routingBox!.y + routingBox!.height),
    ).toBeGreaterThanOrEqual(20);

    await routingCard.getByRole('button', { name: 'View all' }).click();
    await expect(
      routingCard.getByText('Messages', { exact: true }),
    ).toBeVisible();
    await expect(
      routingCard.getByText('Groups', { exact: true }),
    ).toBeVisible();

    await page.getByRole('button', { name: 'Refresh status' }).hover();
    await expect(
      page.getByText('Failed to refresh route status.'),
    ).toBeVisible();

    await page.getByRole('button', { name: 'Test route' }).click();
    const routeDialog = page.getByRole('dialog');
    await expect(
      routeDialog.getByText('Test route', { exact: true }),
    ).toBeVisible();
    await expect(
      routeDialog.getByText(
        'Choose an event to see which processor handles it, or run a test.',
      ),
    ).toBeVisible();
    await expect(routeDialog.getByText('Sample event is ready')).toHaveCount(0);
    await expect(
      routeDialog.getByRole('button', { name: 'Test data' }),
    ).toBeVisible();
    await expect(
      routeDialog.getByRole('button', { name: 'Preview match' }),
    ).toBeVisible();
    await expect(
      routeDialog.getByRole('button', { name: 'Run full test' }),
    ).toBeVisible();
    await routeDialog.getByRole('combobox').first().click();
    await expect(
      page.getByText('Messages', { exact: true }).last(),
    ).toBeVisible();
    await expect(
      page.getByText('Groups', { exact: true }).last(),
    ).toBeVisible();
    await page.keyboard.press('Escape');

    await routeDialog.getByRole('button', { name: 'Preview match' }).click();
    await expect(routeDialog.getByText('Matched route')).toBeVisible();

    await routeDialog.getByRole('button', { name: 'Run full test' }).click();
    await expect(routeDialog.getByText('Matched route')).toHaveCount(0);
    await expect(
      routeDialog.getByText(
        'The bot is not running. Check its platform settings and enable it before running a full test.',
      ),
    ).toBeVisible();
    await expect(routeDialog.getByText('Internal server error')).toHaveCount(0);

    await routeDialog.getByRole('button', { name: 'Preview match' }).click();
    await expect(
      routeDialog.getByText(
        'The bot is not running. Check its platform settings and enable it before running a full test.',
      ),
    ).toHaveCount(0);
    await expect(routeDialog.getByText('Matched route')).toBeVisible();
    const dialogBox = await routeDialog.boundingBox();
    expect(dialogBox).not.toBeNull();
    expect(dialogBox!.height).toBeLessThan(500);
  });

  test('toggles bot enable/disable state', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a bot first
    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Toggle Test Bot');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    // Wait for the enable switch to load (it's fetched via getBot)
    await expect(page.locator('#bot-enable-switch')).toBeVisible({
      timeout: 5000,
    });

    // Verify initial state is enabled
    await expect(page.locator('#bot-enable-switch')).toBeChecked();

    // Toggle to disabled
    await page.locator('#bot-enable-switch').click();
    await expect(page.locator('#bot-enable-switch')).not.toBeChecked();

    // Reload and verify state persisted
    await page.reload();
    await expect(page.locator('#bot-enable-switch')).not.toBeChecked();
  });

  test('switches between bot detail tabs', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a bot
    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Tab Test Bot');
    await submit(page);

    // Verify we're on the Configuration tab
    await expect(
      page.getByRole('tab', { name: /Configuration/ }),
    ).toHaveAttribute('data-state', 'active');
    await expect(
      page.getByRole('button', { name: 'Edit basic information' }),
    ).toBeVisible();

    // Switch to Logs tab
    await page.getByRole('tab', { name: /Logs/ }).click();
    await expect(page.getByRole('tab', { name: /Logs/ })).toHaveAttribute(
      'data-state',
      'active',
    );

    // Switch to Sessions tab
    await page.getByRole('tab', { name: /Sessions/ }).click();
    await expect(page.getByRole('tab', { name: /Sessions/ })).toHaveAttribute(
      'data-state',
      'active',
    );

    // Switch back to Configuration
    await page.getByRole('tab', { name: /Configuration/ }).click();
    await expect(
      page.getByRole('button', { name: 'Edit basic information' }),
    ).toBeVisible();
  });

  test('save button is disabled when form is clean', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a bot
    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Clean Form Bot');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    // Reload the persisted record so post-create initialization has completed.
    await page.reload();
    await expect(
      page.getByRole('heading', { name: 'Clean Form Bot' }),
    ).toBeVisible();

    // After loading, save button should be disabled (form is clean)
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    await expect(saveButton).toBeDisabled();

    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const infoDialog = page.getByRole('dialog');
    await infoDialog.getByLabel('Description').fill('New description');
    await infoDialog.getByRole('button', { name: 'Save' }).click();
    await expect(saveButton).toBeDisabled();
  });

  test('shows validation error when bot name is empty', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/bots?id=new');

    // Select adapter but leave name empty
    await selectPlaywrightAdapter(page);
    await submit(page);

    // Should show validation error for name (zod validation)
    await expect(page.getByText(/cannot be empty/i)).toBeVisible();
    await expect(page).toHaveURL(/\/home\/bots\?id=new$/);
  });
});

test.describe('pipeline advanced flows', () => {
  test('scopes runner tool catalogs to the edited pipeline', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withRunnerToolSelector: true,
    });
    const toolCatalogUrls: URL[] = [];
    const requestedPaths: string[] = [];
    page.on('request', (request) => {
      const url = new URL(request.url());
      if (url.pathname === '/api/v1/tools') toolCatalogUrls.push(url);
      requestedPaths.push(url.pathname);
    });

    await page.goto('/home/agents?id=pipeline-scope');
    await page.getByRole('tab', { name: /^AI$/ }).click();
    await expect(
      page.getByRole('button', { name: 'Edit tools' }),
    ).toBeVisible();

    await expect
      .poll(() =>
        toolCatalogUrls.some(
          (url) => url.searchParams.get('pipeline_uuid') === 'pipeline-scope',
        ),
      )
      .toBe(true);
    await expect
      .poll(() =>
        requestedPaths.includes('/api/v1/pipelines/pipeline-scope/extensions'),
      )
      .toBe(true);
  });

  test('switches to monitoring tab from pipeline detail', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a pipeline
    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();
    await page.locator('input[name="name"]').fill('Tab Test Pipeline');
    await submit(page);

    await expect(
      page.getByRole('region', { name: 'Configuration' }),
    ).toBeVisible();

    // Switch to Monitoring tab (labeled "Dashboard" in the pipeline context)
    // Skip Debug tab as it requires WebSocket connection
    await page
      .getByRole('button', { name: 'Dashboard', exact: true })
      .last()
      .click();
    await expect(page.getByRole('region', { name: /Dashboard/ })).toBeVisible();

    // Switch back to Configuration
    await page
      .getByRole('button', { name: 'Dashboard', exact: true })
      .last()
      .click();
    await expect(
      page.getByRole('region', { name: 'Configuration' }),
    ).toBeVisible();
  });

  test('save button reflects form dirty state', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a pipeline
    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();
    await page.locator('input[name="name"]').fill('Dirty Form Pipeline');
    await submit(page);

    const saveButton = page.getByRole('button', { name: /^Save$/ });
    await expect(saveButton).toBeDisabled();
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const infoDialog = page.getByRole('dialog');
    await infoDialog.getByLabel('Name').fill('Dirty Form Pipeline Updated');
    await infoDialog.getByRole('button', { name: 'Save' }).click();
    await expect(
      page.getByRole('heading', { name: /Dirty Form Pipeline Updated/ }),
    ).toBeVisible();
    await expect(saveButton).toBeDisabled();
  });

  test('shows validation error when pipeline name is empty', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();

    // Submit without filling name
    await submit(page);

    // Should show validation error for name (zod validation)
    await expect(page.getByText(/cannot be empty/i)).toBeVisible();
    await expect(page).toHaveURL(/\/home\/agents\?id=new$/);
  });
});

test.describe('agent runner resource selectors', () => {
  test('uses the global catalog and preserves temporarily unavailable tools', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const toolCatalogUrls: URL[] = [];
    const requestedPaths: string[] = [];
    let savedAgent: Record<string, unknown> | undefined;
    page.on('request', (request) => {
      const url = new URL(request.url());
      requestedPaths.push(url.pathname);
      if (url.pathname === '/api/v1/tools') toolCatalogUrls.push(url);
      if (
        url.pathname === '/api/v1/agents/agent-scope' &&
        request.method() === 'PUT'
      ) {
        savedAgent = JSON.parse(request.postData() || '{}') as Record<
          string,
          unknown
        >;
      }
    });

    await page.goto('/home/agents?id=agent-scope');
    await page.getByRole('tab', { name: /^Runner$/ }).click();
    await page.getByRole('tab', { name: 'Local Agent' }).click();
    await page.getByRole('button', { name: 'Edit tools' }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('available_plugin_tool')).toBeVisible();
    await dialog
      .getByRole('checkbox', { name: 'Select available_plugin_tool' })
      .click();
    await dialog.getByRole('button', { name: /^Confirm$/ }).click();
    await save(page);

    await expect.poll(() => savedAgent).toBeTruthy();
    expect(savedAgent).toMatchObject({
      config: {
        runner_config: {
          'plugin:langbot-team/LocalAgent/default': {
            tools: ['unavailable_plugin_tool', 'available_plugin_tool'],
          },
        },
      },
    });
    expect(
      toolCatalogUrls.some((url) => url.searchParams.has('pipeline_uuid')),
    ).toBe(false);
    expect(requestedPaths).not.toContain(
      '/api/v1/pipelines/agent-scope/extensions',
    );
  });
});

test.describe('agent and pipeline save concurrency', () => {
  test('agent save freezes its payload and keeps later edits dirty', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAdapterEvents: true,
    });
    const delayedSave = await installDelayedFirstSave(
      page,
      '/api/v1/agents/agent-save-race',
    );

    await page.goto('/home/agents?id=agent-save-race');
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    await page.getByRole('tab', { name: 'Bindable Event Range' }).click();
    const eventPatterns = page.getByLabel('Event Range');
    await expect(eventPatterns).toBeVisible();

    await eventPatterns.click();
    await page
      .getByRole('option')
      .filter({ hasText: 'message.received' })
      .click();
    await page.keyboard.press('Escape');
    await saveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(1);
    await expect(saveButton).toBeDisabled();

    await eventPatterns.click();
    await page.getByRole('option').filter({ hasText: 'group.*' }).click();
    await page
      .getByRole('option')
      .filter({ hasText: 'message.received' })
      .click();
    await page.keyboard.press('Escape');
    await forceFormSubmit(page, '#agent-form');
    expect(delayedSave.payloads).toHaveLength(1);
    await expect(saveButton).toBeDisabled();

    delayedSave.releaseFirstSave();
    await expect(saveButton).toBeEnabled();
    expect(delayedSave.payloads[0]).toMatchObject({
      supported_event_patterns: ['message.received'],
    });

    await saveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(2);
    expect(delayedSave.payloads[1]).toMatchObject({
      supported_event_patterns: ['group.*'],
    });
    await expect(saveButton).toBeDisabled();
  });

  test('pipeline save freezes its payload and keeps later edits dirty', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const delayedSave = await installDelayedFirstSave(
      page,
      '/api/v1/pipelines/pipeline-save-race',
    );

    await page.goto('/home/agents?id=pipeline-save-race');
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    let infoDialog = page.getByRole('dialog');
    await infoDialog.getByLabel('Name').fill('Submitted Pipeline');
    const dialogSaveButton = infoDialog.getByRole('button', { name: 'Save' });
    await dialogSaveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(1);
    await expect(
      infoDialog.getByRole('button', { name: 'Saving...' }),
    ).toBeDisabled();

    delayedSave.releaseFirstSave();
    await expect(infoDialog).toHaveCount(0);
    expect(delayedSave.payloads[0]).toMatchObject({
      name: 'Submitted Pipeline',
      description: '',
    });

    await page.getByRole('button', { name: 'Edit basic information' }).click();
    infoDialog = page.getByRole('dialog');
    await infoDialog
      .getByLabel('Description')
      .fill('Edited in the next basic information save');
    await infoDialog.getByRole('button', { name: 'Save' }).click();
    await expect.poll(() => delayedSave.payloads.length).toBe(2);
    expect(delayedSave.payloads[1]).toMatchObject({
      name: 'Submitted Pipeline',
      description: 'Edited in the next basic information save',
    });
    await expect(infoDialog).toHaveCount(0);
  });
});

test.describe('cross-resource flows', () => {
  test('adds custom bot events and reorders routes with a drag preview', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAdapterEvents: true,
    });

    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Routing Bot');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    await page.getByRole('button', { name: 'Add behavior' }).click();
    await expect(
      page.getByText('Common scenarios', { exact: true }),
    ).toBeVisible();
    await page.getByRole('menuitem', { name: /^Reply to messages/ }).click();
    await page.getByRole('button', { name: 'Add behavior' }).click();
    await page.getByRole('menuitem', { name: /^Welcome new members/ }).click();

    const routeCards = page.locator('[data-testid^="event-route-"]');
    await expect(routeCards).toHaveCount(2);
    await expect(routeCards.nth(0)).toContainText('Message received');
    await expect(routeCards.nth(1)).toContainText('Member joined group');

    await page.getByRole('button', { name: 'Add behavior' }).click();
    await page
      .getByRole('menuitem', { name: /^Configure another event/ })
      .hover();
    const eventSubmenu = page.locator(
      '[data-slot="dropdown-menu-sub-content"]',
    );
    await expect(
      eventSubmenu.getByText('Messages', { exact: true }),
    ).toBeVisible();
    await expect(
      eventSubmenu.getByRole('menuitem', { name: /^Message edited/ }),
    ).toBeVisible();
    await eventSubmenu
      .getByRole('menuitem', { name: /^Message edited/ })
      .click();
    await expect(routeCards).toHaveCount(3);
    await expect(routeCards.nth(2)).toContainText('Message edited');

    const firstHandle = page.getByRole('button', { name: 'Drag route 1' });
    const secondCard = routeCards.nth(1);
    const handleBox = await firstHandle.boundingBox();
    const targetBox = await secondCard.boundingBox();
    expect(handleBox).not.toBeNull();
    expect(targetBox).not.toBeNull();

    await page.mouse.move(
      handleBox!.x + handleBox!.width / 2,
      handleBox!.y + handleBox!.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      handleBox!.x + handleBox!.width / 2,
      handleBox!.y + handleBox!.height / 2 + 10,
      { steps: 4 },
    );
    await expect(page.locator('[data-drag-overlay="true"]')).toBeVisible();
    await page.mouse.move(
      targetBox!.x + targetBox!.width / 2,
      targetBox!.y + targetBox!.height - 4,
      { steps: 12 },
    );
    await page.mouse.up();

    await expect(page.locator('[data-drag-overlay="true"]')).toHaveCount(0);
    await expect(routeCards.nth(0)).toContainText('Member joined group');
    await expect(routeCards.nth(1)).toContainText('Message received');

    await save(page);
    await page.reload();
    const savedRouteCards = page.locator('[data-testid^="event-route-"]');
    await expect(savedRouteCards.nth(0)).toContainText('Member joined group');
    await expect(savedRouteCards.nth(1)).toContainText('Message received');
    await expect(savedRouteCards.nth(2)).toContainText('Message edited');
  });

  test('creates a pipeline then binds it to a bot', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a pipeline first
    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();
    await page.locator('input[name="name"]').fill('Production Pipeline');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/agents\?id=pipeline-1$/);

    // Create a bot
    await page.goto('/home/bots?id=new');
    await selectPlaywrightAdapter(page);
    await page.locator('input[name="name"]').fill('Bound Bot');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    // Wait for form to fully load
    await expect(
      page.getByRole('heading', { name: 'Bound Bot' }),
    ).toBeVisible();

    await page.getByRole('button', { name: 'Add behavior' }).click();
    await page.getByRole('menuitem', { name: /^Reply to messages/ }).click();
    await page
      .getByRole('combobox')
      .filter({ hasText: 'Select processor' })
      .click();

    // Select the pipeline option
    await page.getByRole('option', { name: /Production Pipeline/ }).click();

    // Save the bot
    await save(page);

    // Reload and verify binding persisted
    await page.reload();
    // The pipeline name should appear in the select trigger (not in sidebar or options)
    await expect(
      page.getByRole('combobox').filter({ hasText: 'Production Pipeline' }),
    ).toBeVisible();
  });
});

test.describe('empty states', () => {
  test('shows empty state when no bots exist', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/bots');
    await expect(page.getByText('Select a bot from the sidebar')).toBeVisible();
  });

  test('shows empty state when no processors exist', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/agents');
    await expect(
      page.getByText('Select an Agent or Pipeline from the sidebar'),
    ).toBeVisible();
  });

  test('shows empty state when no knowledge bases exist', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/knowledge');
    await expect(
      page.getByText('Select a knowledge base from the sidebar'),
    ).toBeVisible();
  });

  test('shows empty state when no MCP servers exist', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/mcp');
    await expect(
      page.getByText('Select an MCP server from the sidebar'),
    ).toBeVisible();
  });
});

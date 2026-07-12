import { expect, Page, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

async function save(page: Page) {
  const button = page.getByRole('button', { name: /^Save$/ });
  await expect(button).toBeEnabled();
  await button.click();
}

async function submit(page: Page) {
  await page.getByRole('button', { name: /^Submit$/ }).click();
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
  test('creates, edits, and deletes a bot', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/bots?id=new');

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await page.locator('input[name="name"]').fill('Support Bot');
    await page
      .locator('input[name="description"]')
      .fill('Answers customer support questions.');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
    await submit(page);

    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
    await page.reload();
    await expect(page.locator('input[name="name"]')).toHaveValue('Support Bot');

    await page
      .locator('input[name="description"]')
      .fill('Answers customer support questions with context.');
    await save(page);
    await expect(page.locator('input[name="description"]')).toHaveValue(
      'Answers customer support questions with context.',
    );

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
    await expect(page.locator('input[name="basic.name"]')).toHaveValue(
      'Escalation Pipeline',
    );

    await page
      .locator('input[name="basic.description"]')
      .fill('Routes urgent customer issues to operators.');
    await save(page);
    await expect(page.locator('input[name="basic.description"]')).toHaveValue(
      'Routes urgent customer issues to operators.',
    );

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

    await expect(page.locator('input[name="basic.name"]')).toBeVisible();
    await page.getByRole('button', { name: /^AI$/ }).click();

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
    await expect(page.locator('input[name="name"]')).toHaveValue(
      'Support Knowledge',
    );
    await page.waitForTimeout(600);

    await page
      .locator('input[name="description"]')
      .fill('Updated source material for support answers.');
    await save(page);
    await expect(page.locator('input[name="description"]')).toHaveValue(
      'Updated source material for support answers.',
    );

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
  test('toggles bot enable/disable state', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a bot first
    await page.goto('/home/bots?id=new');
    await page.locator('input[name="name"]').fill('Toggle Test Bot');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
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
    await page.locator('input[name="name"]').fill('Tab Test Bot');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
    await submit(page);

    // Verify we're on the Configuration tab
    await expect(
      page.getByRole('tab', { name: /Configuration/ }),
    ).toHaveAttribute('data-state', 'active');
    await expect(page.locator('input[name="name"]')).toBeVisible();

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
    await expect(page.locator('input[name="name"]')).toBeVisible();
  });

  test('save button is disabled when form is clean', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a bot
    await page.goto('/home/bots?id=new');
    await page.locator('input[name="name"]').fill('Clean Form Bot');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
    await submit(page);

    // After creation, save button should be disabled (form is clean)
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    await expect(saveButton).toBeDisabled();

    // Edit the form
    await page.locator('input[name="description"]').fill('New description');
    await expect(saveButton).toBeEnabled();

    // Save
    await saveButton.click();
    await expect(saveButton).toBeDisabled();
  });

  test('shows validation error when bot name is empty', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/bots?id=new');

    // Select adapter but leave name empty
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
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
    await page.getByRole('button', { name: /^AI$/ }).click();
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

    // Verify we're on the Configuration tab
    await expect(
      page.getByRole('tab', { name: /Configuration/ }),
    ).toHaveAttribute('data-state', 'active');

    // Switch to Monitoring tab (labeled "Dashboard" in the pipeline context)
    // Skip Debug tab as it requires WebSocket connection
    await page.getByRole('tab', { name: /Dashboard/ }).click();
    await expect(page.getByRole('tab', { name: /Dashboard/ })).toHaveAttribute(
      'data-state',
      'active',
    );

    // Switch back to Configuration
    await page.getByRole('tab', { name: /Configuration/ }).click();
    await expect(page.locator('input[name="basic.name"]')).toBeVisible();
  });

  test('save button reflects form dirty state', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a pipeline
    await page.goto('/home/agents?id=new');
    await page.getByRole('button', { name: /^Pipeline/ }).click();
    await page.locator('input[name="name"]').fill('Dirty Form Pipeline');
    await submit(page);

    // Wait for the page to fully load and form to reset
    await page.waitForTimeout(500);

    // Edit the form - use the name field which definitely triggers dirty state
    await page
      .locator('input[name="basic.name"]')
      .fill('Dirty Form Pipeline Updated');
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    await expect(saveButton).toBeEnabled();

    // Save
    await saveButton.click();
    // Wait for save to complete
    await page.waitForTimeout(500);
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
    await page.getByRole('button', { name: /^Runner$/ }).click();
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
    await installLangBotApiMocks(page, { authenticated: true });
    const delayedSave = await installDelayedFirstSave(
      page,
      '/api/v1/agents/agent-save-race',
    );

    await page.goto('/home/agents?id=agent-save-race');
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    const nameInput = page.locator('input[name="basic.name"]');
    const descriptionInput = page.locator('input[name="basic.description"]');
    await expect(nameInput).toBeVisible();

    await nameInput.fill('Submitted Agent');
    await saveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(1);
    await expect(saveButton).toBeDisabled();

    await descriptionInput.fill('Edited while the agent save is pending');
    await forceFormSubmit(page, '#agent-form');
    expect(delayedSave.payloads).toHaveLength(1);
    await expect(saveButton).toBeDisabled();

    delayedSave.releaseFirstSave();
    await expect(saveButton).toBeEnabled();
    expect(delayedSave.payloads[0]).toMatchObject({
      name: 'Submitted Agent',
      description: '',
    });

    await saveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(2);
    expect(delayedSave.payloads[1]).toMatchObject({
      name: 'Submitted Agent',
      description: 'Edited while the agent save is pending',
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
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    const nameInput = page.locator('input[name="basic.name"]');
    const descriptionInput = page.locator('input[name="basic.description"]');
    await expect(nameInput).toBeVisible();

    await nameInput.fill('Submitted Pipeline');
    await saveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(1);
    await expect(saveButton).toBeDisabled();

    await descriptionInput.fill('Edited while the pipeline save is pending');
    await forceFormSubmit(page, '#pipeline-form');
    expect(delayedSave.payloads).toHaveLength(1);
    await expect(saveButton).toBeDisabled();

    delayedSave.releaseFirstSave();
    await expect(saveButton).toBeEnabled();
    expect(delayedSave.payloads[0]).toMatchObject({
      name: 'Submitted Pipeline',
      description: '',
    });

    await saveButton.click();
    await expect.poll(() => delayedSave.payloads.length).toBe(2);
    expect(delayedSave.payloads[1]).toMatchObject({
      name: 'Submitted Pipeline',
      description: 'Edited while the pipeline save is pending',
    });
    await expect(saveButton).toBeDisabled();
  });
});

test.describe('cross-resource flows', () => {
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
    await page.locator('input[name="name"]').fill('Bound Bot');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
    await submit(page);
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    // Wait for form to fully load
    await expect(page.locator('input[name="name"]')).toHaveValue('Bound Bot');

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

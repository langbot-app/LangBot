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

    await page.goto('/home/pipelines?id=new');

    await expect(page.locator('input[name="basic.name"]')).toBeVisible();
    await page.locator('input[name="basic.name"]').fill('Escalation Pipeline');
    await page
      .locator('input[name="basic.description"]')
      .fill('Routes urgent customer issues.');
    await submit(page);

    await expect(page).toHaveURL(/\/home\/pipelines\?id=pipeline-1$/);
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

    await expect(page).toHaveURL(/\/home\/pipelines$/);
    await expect(
      page.getByText('Select a pipeline from the sidebar'),
    ).toBeVisible();
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
  test('switches to monitoring tab from pipeline detail', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a pipeline
    await page.goto('/home/pipelines?id=new');
    await page.locator('input[name="basic.name"]').fill('Tab Test Pipeline');
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
    await page.goto('/home/pipelines?id=new');
    await page.locator('input[name="basic.name"]').fill('Dirty Form Pipeline');
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

    await page.goto('/home/pipelines?id=new');

    // Submit without filling name
    await submit(page);

    // Should show validation error for name (zod validation)
    await expect(page.getByText(/cannot be empty/i)).toBeVisible();
    await expect(page).toHaveURL(/\/home\/pipelines\?id=new$/);
  });
});

test.describe('cross-resource flows', () => {
  test('creates a pipeline then binds it to a bot', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    // Create a pipeline first
    await page.goto('/home/pipelines?id=new');
    await page.locator('input[name="basic.name"]').fill('Production Pipeline');
    await submit(page);
    await expect(page).toHaveURL(/\/home\/pipelines\?id=pipeline-1$/);

    // Create a bot
    await page.goto('/home/bots?id=new');
    await page.locator('input[name="name"]').fill('Bound Bot');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
    await submit(page);
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);

    // Wait for form to fully load
    await expect(page.locator('input[name="name"]')).toHaveValue('Bound Bot');

    // Find the pipeline select by its label "Bind Pipeline"
    const pipelineCard = page.getByText('Bind Pipeline').locator('..');
    await expect(pipelineCard).toBeVisible({ timeout: 5000 });

    // Click on the select trigger within the pipeline binding card
    // The select trigger shows "Select Pipeline" placeholder initially
    const pipelineSelectTrigger = page.getByText('Select Pipeline').first();
    await pipelineSelectTrigger.click();

    // Select the pipeline option
    await page.getByRole('option', { name: 'Production Pipeline' }).click();

    // Save the bot
    await save(page);

    // Reload and verify binding persisted
    await page.reload();
    // The pipeline name should appear in the select trigger (not in sidebar or options)
    await expect(
      page
        .locator('[data-slot="select-trigger"]')
        .filter({ hasText: 'Production Pipeline' }),
    ).toBeVisible();
  });
});

test.describe('empty states', () => {
  test('shows empty state when no bots exist', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/bots');
    await expect(page.getByText('Select a bot from the sidebar')).toBeVisible();
  });

  test('shows empty state when no pipelines exist', async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/pipelines');
    await expect(
      page.getByText('Select a pipeline from the sidebar'),
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

import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

function wrapped(data: unknown) {
  return JSON.stringify({
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  });
}

async function fulfill(
  route: Parameters<Parameters<import('@playwright/test').Page['route']>[1]>[0],
  data: unknown,
) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: wrapped(data),
  });
}

test('quota-reached create actions are disabled and explain the current limit', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });

  await page.route('**/api/v1/system/info', (route) =>
    fulfill(route, {
      debug: false,
      version: 'quota-e2e',
      edition: 'community',
      cloud_service_url: 'https://space.langbot.app',
      enable_marketplace: true,
      allow_modify_login_info: true,
      disable_models_service: false,
      limitation: {
        max_bots: 2,
        max_pipelines: 3,
        max_extensions: 3,
        max_knowledge_bases: 2,
      },
      outbound_ips: [],
      wizard_status: 'completed',
      wizard_progress: null,
    }),
  );
  await page.route('**/api/v1/platform/bots**', (route) =>
    fulfill(route, {
      bots: Array.from({ length: 2 }, (_, index) => ({
        uuid: `bot-${index}`,
        name: `Bot ${index + 1}`,
        description: '',
        adapter: 'aiocqhttp',
        enable: true,
        updated_at: new Date().toISOString(),
      })),
    }),
  );
  await page.route('**/api/v1/agents', (route) =>
    fulfill(route, {
      agents: Array.from({ length: 3 }, (_, index) => ({
        uuid: `pipeline-${index}`,
        name: `Pipeline ${index + 1}`,
        description: '',
        emoji: '⚙️',
        kind: 'pipeline',
        updated_at: new Date().toISOString(),
      })),
    }),
  );
  await page.route('**/api/v1/knowledge/bases**', (route) =>
    fulfill(route, {
      bases: Array.from({ length: 2 }, (_, index) => ({
        uuid: `kb-${index}`,
        name: `Knowledge ${index + 1}`,
        description: '',
        emoji: '📚',
        updated_at: new Date().toISOString(),
      })),
    }),
  );
  await page.route('**/api/v1/plugins**', (route) =>
    fulfill(route, { plugins: [] }),
  );
  await page.route('**/api/v1/mcp/servers**', (route) =>
    fulfill(route, {
      servers: Array.from({ length: 3 }, (_, index) => ({
        name: `mcp-${index}`,
        mode: 'http',
        enable: true,
        runtime_info: { status: 'connected' },
      })),
    }),
  );
  await page.route('**/api/v1/skills**', (route) =>
    fulfill(route, { skills: [] }),
  );

  await page.goto('/home/bots');

  const botCreate = page.getByRole('button', {
    name: 'Create Bots',
    exact: true,
  });
  const processorCreate = page.getByRole('button', {
    name: 'Create Processors',
    exact: true,
  });
  const knowledgeCreate = page.getByRole('button', {
    name: 'Create Knowledge',
    exact: true,
  });
  const addExtension = page.getByRole('button', {
    name: 'Add Extension',
    exact: true,
  });

  await expect(botCreate).toBeDisabled();
  await expect(processorCreate).toBeDisabled();
  await expect(knowledgeCreate).toBeDisabled();
  await expect(addExtension).toBeEnabled();

  const botQuotaTrigger = botCreate.locator('..');
  await botQuotaTrigger.hover();
  await expect(
    page.getByText(
      'The Bots limit (2) for this workspace has been reached. Delete one existing item before creating another.',
    ),
  ).toBeVisible();
  await botQuotaTrigger.focus();
  await expect(botQuotaTrigger).toBeFocused();
  await expect(
    page.getByText(
      'The Bots limit (2) for this workspace has been reached. Delete one existing item before creating another.',
    ),
  ).toBeVisible();

  await addExtension.click();
  await expect(page).toHaveURL(/\/home\/add-extension$/);
  const manualAdd = page.getByRole('button', { name: 'Manual Add' });
  await expect(manualAdd).toBeDisabled();
  await manualAdd.locator('..').hover();
  await expect(
    page.getByText(
      'The Extensions limit (3) for this workspace has been reached. Delete one existing item before creating another.',
    ),
  ).toBeVisible();
});

for (const kind of ['plugin', 'skill'] as const) {
  test(`GitHub ${kind} confirmation rejects a failed quota check and can retry`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.route('**/api/v1/system/info', (route) =>
      fulfill(route, {
        debug: false,
        version: 'quota-e2e',
        edition: 'community',
        cloud_service_url: 'https://space.langbot.app',
        enable_marketplace: true,
        allow_modify_login_info: true,
        disable_models_service: false,
        limitation: { max_extensions: 3 },
        outbound_ips: [],
        wizard_status: 'completed',
        wizard_progress: null,
      }),
    );

    let checkingQuota = false;
    let quotaChecks = 0;
    let releaseQuotaCheck!: () => void;
    const quotaCheckGate = new Promise<void>((resolve) => {
      releaseQuotaCheck = resolve;
    });
    await page.route('**/api/v1/plugins', async (route) => {
      if (checkingQuota) {
        quotaChecks += 1;
        await quotaCheckGate;
        checkingQuota = false;
        await route.fulfill({
          status: 503,
          json: { code: 503, message: 'Quota service unavailable' },
        });
        return;
      }
      await fulfill(route, { plugins: [] });
    });

    const skillUrl =
      'https://github.com/quota-fixture/extension/blob/main/SKILL.md';
    await page.route('**/api/v1/plugins/github/releases', (route) =>
      fulfill(route, {
        owner: 'quota-fixture',
        repo: 'extension',
        releases: [
          {
            id: 7,
            tag_name: 'v1.0.0',
            name: 'Quota Test Release',
            published_at: '2026-01-01T00:00:00Z',
            prerelease: false,
            draft: false,
          },
        ],
      }),
    );
    await page.route('**/api/v1/plugins/github/release-assets', (route) =>
      fulfill(route, {
        assets: [
          {
            id: 42,
            name: 'quota-test.lbpkg',
            size: 1024,
            download_url: 'https://example.com/quota-test.lbpkg',
            content_type: 'application/octet-stream',
          },
        ],
      }),
    );
    await page.route('**/api/v1/skills/install/github/preview', (route) =>
      fulfill(route, {
        skills: [
          {
            name: 'quota-test-skill',
            display_name: 'Quota Test Skill',
            description: 'Skill used to verify quota confirmation',
            instructions: '# Quota Test Skill',
            package_root: '.',
          },
        ],
      }),
    );

    const installRequests: { path: string; method: string; body: unknown }[] =
      [];
    await page.route(
      /\/api\/v1\/(plugins|skills)\/install\/github$/,
      (route) => {
        const request = route.request();
        installRequests.push({
          path: new URL(request.url()).pathname,
          method: request.method(),
          body: request.postDataJSON(),
        });
        return fulfill(
          route,
          kind === 'plugin' ? { task_id: 'quota-test-task' } : { skills: [] },
        );
      },
    );

    await page.goto('/home/add-extension');
    await page.getByRole('button', { name: 'Manual Add', exact: true }).click();
    await page.getByRole('button', { name: 'Install from GitHub' }).click();
    await page
      .getByPlaceholder('GitHub repository, Release, or SKILL.md link')
      .fill(
        kind === 'plugin'
          ? 'https://github.com/quota-fixture/extension'
          : skillUrl,
      );
    const confirm = page.getByRole('button', { name: 'Confirm', exact: true });
    await confirm.click();
    if (kind === 'plugin') {
      await page.getByText('Quota Test Release', { exact: true }).click();
      await page.getByText('quota-test.lbpkg', { exact: true }).click();
    } else {
      await expect(
        page.getByText('Quota Test Skill', { exact: true }),
      ).toBeVisible();
    }

    checkingQuota = true;
    await confirm.click();
    try {
      await expect.poll(() => quotaChecks).toBe(1);
      await expect(
        page.getByText(`Installing ${kind}...`, { exact: true }),
      ).toBeVisible();
      await expect(confirm).toHaveCount(0);
      await page.keyboard.press('Enter');
      expect(quotaChecks).toBe(1);
      expect(installRequests).toEqual([]);
    } finally {
      releaseQuotaCheck();
    }

    await expect(
      page.getByText(
        'Unable to verify the current workspace quota. Please try again.',
      ),
    ).toBeVisible();
    expect(installRequests).toEqual([]);
    await expect(confirm).toBeEnabled();

    await confirm.click();
    await expect.poll(() => installRequests.length).toBe(1);
    await expect(
      page.getByRole('button', {
        name: 'Manual Add',
        exact: true,
        includeHidden: true,
      }),
    ).toHaveAttribute('aria-expanded', 'false');
    await expect(
      page.getByPlaceholder('GitHub repository, Release, or SKILL.md link'),
    ).toBeHidden();
    expect(installRequests).toEqual([
      {
        path: `/api/v1/${kind === 'plugin' ? 'plugins' : 'skills'}/install/github`,
        method: 'POST',
        body:
          kind === 'plugin'
            ? {
                asset_id: 42,
                release_id: 7,
                owner: 'quota-fixture',
                repo: 'extension',
                release_tag: 'v1.0.0',
              }
            : {
                asset_url: skillUrl,
                owner: 'quota-fixture',
                repo: 'extension',
                release_tag: 'main',
              },
      },
    ]);
    if (kind === 'skill') {
      await expect(
        page.getByText('Skill installed successfully', { exact: true }),
      ).toBeVisible();
    }
  });
}

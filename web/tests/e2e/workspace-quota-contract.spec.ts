import { expect, test, type Page } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

const unlimited = {
  max_bots: -1,
  max_pipelines: -1,
  max_knowledge_bases: -1,
  max_extensions: -1,
};
const resourceLimits = { bots: 2, pipelines: 3, knowledge: 4, extensions: 6 };
const fields = {
  bots: 'max_bots',
  pipelines: 'max_pipelines',
  knowledge: 'max_knowledge_bases',
  extensions: 'max_extensions',
} as const;
const labels = {
  bots: 'Create Bots',
  pipelines: 'Create Processors',
  knowledge: 'Create Knowledge',
} as const;
const types = ['plugin', 'mcp', 'skill'] as const;
const marketplaceEntry = (label: string, type: (typeof types)[number]) => ({
  id: 1,
  author: 'quota-qa',
  name: label.toLowerCase().replaceAll(' ', '-'),
  label: { en_US: label },
  description: { en_US: `${label} description` },
  type,
  latest_version: '1.0.0',
  install_count: 0,
  like_count: 0,
  components: {},
  tags: [],
  repository: 'https://example.invalid/extension',
  icon: '',
  created_at: '',
  updated_at: '',
});

async function installQuotaFixtures(
  page: Page,
  source: 'local' | 'cloud_projection',
  limits: typeof unlimited,
) {
  const workspace = {
    ...makeWorkspaceEntry('workspace-playwright', 'Quota workspace', source),
    limitation:
      source === 'cloud_projection'
        ? limits
        : {
            max_bots: 0,
            max_pipelines: 0,
            max_knowledge_bases: 0,
            max_extensions: 0,
          },
  };
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  const installationPosts: string[] = [];
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      /\/(plugins|skills|mcp)\//.test(request.url())
    )
      installationPosts.push(request.url());
  });
  const fulfill = (
    route: Parameters<Parameters<Page['route']>[1]>[0],
    data: unknown,
  ) => route.fulfill({ json: { code: 0, data } });
  await page.route('**/api/v1/system/info', (route) =>
    fulfill(route, {
      debug: false,
      version: 'quota-contract',
      edition: 'community',
      cloud_service_url: 'https://space.langbot.app',
      enable_marketplace: true,
      allow_modify_login_info: true,
      disable_models_service: false,
      limitation: source === 'local' ? limits : unlimited,
      outbound_ips: [],
      wizard_status: 'completed',
      wizard_progress: null,
    }),
  );
  await page.route('**/api/v1/platform/bots', (route) =>
    fulfill(route, {
      bots: Array.from({ length: 2 }, (_, i) => ({
        uuid: `quota-bot-${i}`,
        name: `Quota Bot ${i}`,
        description: '',
        adapter: 'aiocqhttp',
        enable: true,
        updated_at: '2026-03-08T10:00:00Z',
      })),
    }),
  );
  await page.route('**/api/v1/agents', (route) =>
    fulfill(route, {
      agents: Array.from({ length: 3 }, (_, i) => ({
        uuid: `quota-pipeline-${i}`,
        name: `Quota Pipeline ${i}`,
        description: '',
        kind: 'pipeline',
        updated_at: '2026-03-08T10:00:00Z',
      })),
    }),
  );
  await page.route('**/api/v1/knowledge/bases', (route) =>
    fulfill(route, {
      bases: Array.from({ length: 4 }, (_, i) => ({
        uuid: `quota-kb-${i}`,
        name: `Quota Knowledge ${i}`,
        description: '',
        updated_at: '2026-03-08T10:00:00Z',
      })),
    }),
  );
  await page.route('**/api/v1/plugins', (route) =>
    fulfill(route, {
      plugins: [
        {
          plugin_id: 'quota-qa/installed-plugin',
          install_source: 'marketplace',
          debug: false,
          manifest: {
            manifest: {
              metadata: {
                author: 'quota-qa',
                name: 'installed-plugin',
                label: { en_US: 'Installed plugin' },
                version: '1.0.0',
              },
              spec: {},
            },
          },
        },
      ],
    }),
  );
  await page.route('**/api/v1/mcp/servers', (route) =>
    fulfill(route, {
      servers: Array.from({ length: 2 }, (_, i) => ({
        name: `installed-mcp-${i}`,
        enable: true,
        runtime_info: { status: 'connected' },
      })),
    }),
  );
  await page.route('**/api/v1/skills', (route) =>
    fulfill(route, {
      skills: Array.from({ length: 3 }, (_, i) => ({
        name: `installed-skill-${i}`,
        display_name: `Installed skill ${i}`,
        description: '',
        updated_at: '2026-03-08T10:00:00Z',
      })),
    }),
  );
  const grid = types.map((type) => marketplaceEntry(`Grid ${type}`, type));
  const recommended = types.map((type) =>
    marketplaceEntry(`Recommended ${type}`, type),
  );
  await page.route('**/api/v1/marketplace/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/recommendation-lists'))
      return fulfill(route, {
        lists: recommended.map((plugin, i) => ({
          uuid: `recommendation-${i}`,
          label: { en_US: `${plugin.type} picks` },
          sort_order: i,
          plugins: [plugin],
        })),
      });
    if (path.endsWith('/extensions/search'))
      return fulfill(route, { extensions: grid, total: grid.length });
    if (path.endsWith('/search') || path.endsWith('/plugins'))
      return fulfill(route, { plugins: grid, total: grid.length });
    const plugin = [...grid, ...recommended].find((entry) =>
      decodeURIComponent(path).endsWith(`/quota-qa/${entry.name}`),
    );
    if (plugin) return fulfill(route, { plugin });
    return route.fallback();
  });
  return {
    installationPosts,
    cards: [...grid, ...recommended].map((entry) => entry.label.en_US),
  };
}

for (const source of ['local', 'cloud_projection'] as const) {
  for (const resource of Object.keys(
    resourceLimits,
  ) as (keyof typeof resourceLimits)[]) {
    test(`${source}: only the ${resource} resource is blocked at its own quota`, async ({
      page,
    }) => {
      const limits = {
        ...unlimited,
        [fields[resource]]: resourceLimits[resource],
      };
      await installQuotaFixtures(page, source, limits);
      await page.goto('/home/bots');
      for (const [key, label] of Object.entries(labels)) {
        const button = page.getByRole('button', { name: label, exact: true });
        if (key !== resource) await expect(button).toBeEnabled();
      }
      if (resource !== 'extensions') {
        await expect(
          page.getByRole('button', {
            name: labels[resource as keyof typeof labels],
            exact: true,
          }),
        ).toBeDisabled();
      }
      await page
        .getByRole('button', { name: 'Add Extension', exact: true })
        .click();
      const manual = page.getByRole('button', {
        name: 'Manual Add',
        exact: true,
      });
      if (resource === 'extensions') {
        await expect(manual).toBeDisabled();
        await manual.locator('..').focus();
        await expect(
          page.getByText(
            'The Extensions limit (6) for this workspace has been reached. Delete one existing item before creating another.',
            { exact: true },
          ),
        ).toBeVisible();
      } else await expect(manual).toBeEnabled();
      if (resource !== 'extensions') {
        const button = page.getByRole('button', {
          name: labels[resource as keyof typeof labels],
          exact: true,
        });
        await button.locator('..').focus();
        await expect(
          page.getByText(
            `The ${labels[resource as keyof typeof labels].slice(7)} limit (${resourceLimits[resource]}) for this workspace has been reached. Delete one existing item before creating another.`,
            { exact: true },
          ),
        ).toBeVisible();
      }
    });
  }

  test(`${source}: every grid, recommended and manual install entry respects the mixed extension quota`, async ({
    page,
  }) => {
    const limits = { ...unlimited, max_extensions: 6 };
    const { cards, installationPosts } = await installQuotaFixtures(
      page,
      source,
      limits,
    );
    await page.goto('/home/add-extension');
    await expect(
      page.getByRole('button', { name: 'Manual Add', exact: true }),
    ).toBeDisabled();
    for (const name of cards) {
      const card = page.getByRole('group', {
        name: `Install ${name}`,
        exact: true,
      });
      await expect(card).toHaveAttribute('aria-disabled', 'true');
      await card.focus();
      await page.keyboard.press('Enter');
      await expect(page.getByRole('dialog')).toHaveCount(0);
    }
    expect(installationPosts).toEqual([]);

    // One free slot enables every entry again, including each recommended type.
    limits.max_extensions = 7;
    await page.reload();
    await expect(
      page.getByRole('button', { name: 'Manual Add', exact: true }),
    ).toBeEnabled();
    for (const name of cards) {
      const card = page.getByRole('button', {
        name: `Install ${name}`,
        exact: true,
      });
      await expect(card).toHaveAttribute('aria-disabled', 'false');
      await card.click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
    }
    expect(installationPosts).toEqual([]);
  });
}

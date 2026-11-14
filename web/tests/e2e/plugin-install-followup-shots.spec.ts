/**
 * Screenshot evidence for #2804 / #2963: the post-install follow-up steps.
 *
 * Renders the real component tree against the normal API mocks and saves PNGs
 * of the done state for three plugin shapes, so the acceptance criteria can be
 * checked by eye rather than by reading a mapping function:
 *
 *   multi   Runner + Tool + Command + KnowledgeEngine -> one link per distinct
 *           step (agents, pipelines, knowledge) and the pipeline step only once
 *   parser  Parser only -> no follow-up, the banner stays a single line
 *   review  a multi-component plugin still awaiting permission review -> the
 *           Review button keeps the banner, no follow-up competes with it
 *
 * Run: pnpm exec playwright test plugin-install-followup-shots.spec.ts \
 *        --config playwright.permissions.config.ts
 */

import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

const SHOTS = process.env.SHOT_DIR || 'test-results/followup-shots';

const KINDS = {
  multi: ['Runner', 'Tool', 'Command', 'KnowledgeEngine'],
  parser: ['Parser'],
  review: ['Runner', 'Tool'],
} as const;

type Shape = keyof typeof KINDS;

function pluginFor(author: string, name: string, kinds: readonly string[]) {
  return {
    permission_status: {
      compatibility_mode: false,
      pending_confirmation: author === 'qa-review',
    },
    install_source: 'marketplace',
    install_info: {},
    debug: false,
    manifest: {
      manifest: {
        metadata: {
          author,
          name,
          label: { en_US: `${name} fixture` },
          version: '1.0.0',
          description: { en_US: 'follow-up screenshot fixture' },
        },
        spec: {},
      },
    },
    components: kinds.map((kind) => ({
      component_config: {},
      manifest: {
        manifest: {
          apiVersion: 'v1',
          kind,
          metadata: { name: `${kind}-1`, label: { en_US: kind } },
          spec: {},
        },
      },
    })),
  };
}

async function shoot(
  page: import('@playwright/test').Page,
  shape: Shape,
  locale?: string,
) {
  const author = shape === 'review' ? 'qa-review' : 'qa';
  const name = `${shape}-followup`;
  const plugin = pluginFor(author, name, KINDS[shape]);

  await page.route('**/api/v1/plugins', (route) =>
    route.fulfill({ json: { code: 0, data: { plugins: [plugin] } } }),
  );
  await page.route(`**/api/v1/plugins/${author}/${name}`, (route) =>
    route.fulfill({ json: { code: 0, data: { plugin } } }),
  );
  await page.route('**/api/v1/extensions', (route) =>
    route.fulfill({
      json: { code: 0, data: { extensions: [{ type: 'plugin', plugin }] } },
    }),
  );

  // One completed install task, already in the done state.
  const task = {
    id: 90,
    name: `plugin-install-${author}-${name}`,
    label: `${author}/${name}`,
    created_at: 1_700_000_000,
    runtime: { done: true, exception: null },
    task_context: {
      current_action: 'Plugin installed',
      metadata: {
        plugin_name: `${author}/${name}`,
        operation: 'install',
        pending_permission_confirmation: shape === 'review',
      },
    },
  };
  await page.route('**/api/v1/system/tasks?**', (route) =>
    route.fulfill({ json: { code: 0, data: { tasks: [task] } } }),
  );
  await page.route('**/api/v1/system/tasks/90', (route) =>
    route.fulfill({ json: { code: 0, data: task } }),
  );

  await page.goto('/home/extensions');
  // The label is localized, so match every locale's wording.
  const queue = page.getByRole('button', {
    name: /Plugin Tasks|插件任务|安裝任務/,
  });
  await queue.click();
  // The task label also appears in the page behind the popover.
  await page
    .locator('[data-radix-popper-content-wrapper]')
    .getByText(`${author}/${name}`, { exact: true })
    .click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  // The success banner is the anchor both the follow-up and the review live in.
  await expect(
    dialog
      .getByText(
        shape === 'review'
          ? /Permission confirmation required|需要确认插件权限|需要確認插件權限/
          : /Installation successful|安装成功|安裝成功/,
      )
      .first(),
  ).toBeVisible();

  await page.screenshot({
    path: `${SHOTS}/${shape}${locale ? `-${locale}` : ''}.png`,
    fullPage: true,
  });
  return dialog;
}

test('multi-component install shows one link per distinct next step', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const dialog = await shoot(page, 'multi');

  await expect(
    dialog.getByRole('link', { name: /Create an Agent/i }),
  ).toBeVisible();
  await expect(
    dialog.getByRole('link', { name: /Create a pipeline/i }),
  ).toHaveCount(1);
  await expect(
    dialog.getByRole('link', { name: /knowledge base/i }),
  ).toBeVisible();
});

test('parser-only install keeps the banner a single line', async ({ page }) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const dialog = await shoot(page, 'parser');
  await expect(dialog.getByRole('group', { name: /Next steps/i })).toHaveCount(
    0,
  );
});

test('pending permission review wins over the follow-up', async ({ page }) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const dialog = await shoot(page, 'review');
  await expect(
    dialog.getByRole('link', { name: /Review permissions|审阅权限|審閱權限/ }),
  ).toBeVisible();
  await expect(dialog.getByRole('group', { name: /Next steps/i })).toHaveCount(
    0,
  );
});

test('the pending-review list button is short but fully labelled', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const plugin = {
    permission_status: {
      compatibility_mode: false,
      pending_confirmation: true,
    },
    install_source: 'marketplace',
    install_info: {},
    debug: false,
    manifest: {
      manifest: {
        metadata: {
          author: 'qa-review',
          name: 'list-review',
          label: { en_US: 'list-review fixture' },
          version: '1.0.0',
          description: { en_US: 'pending review fixture' },
        },
        spec: {},
      },
    },
    components: [],
  };
  await page.route('**/api/v1/plugins', (route) =>
    route.fulfill({ json: { code: 0, data: { plugins: [plugin] } } }),
  );
  await page.route('**/api/v1/extensions', (route) =>
    route.fulfill({
      json: { code: 0, data: { extensions: [{ type: 'plugin', plugin }] } },
    }),
  );
  await page.goto('/home/extensions');

  // The amber section lists the plugin with its own button, outside the dialog.
  const section = page.getByRole('region', {
    name: /Permission confirmation required/i,
  });
  const button = section.getByRole('button', { name: /Review permissions/i });
  await expect(button).toBeVisible();
  // Visible text is the short form; the phrase lives in the label.
  await expect(button).toHaveText('Review');
  await page.screenshot({
    path: `${SHOTS}/review-list.png`,
    fullPage: true,
  });
});

/**
 * Chinese rendering. The follow-up is user-facing copy, so it must read as
 * natural Chinese rather than a translated English sentence: no repeated
 * "这个插件" in every line, and the traditional locale has to use the same
 * word for a plugin as the rest of its own file (插件, not 外掛).
 */
test.describe('chinese', () => {
  for (const [locale, expected] of [
    ['zh-Hans', ['新建 Agent 或插件处理器', '创建流水线']],
    ['zh-Hant', ['建立 Agent 或插件處理器', '建立流水線']],
  ] as const) {
    test(`${locale} review button stays short with a full label`, async ({
      page,
    }) => {
      await installLangBotApiMocks(page, {
        authenticated: true,
        language: locale,
      });
      const dialog = await shoot(page, 'review', locale);
      const button = dialog.getByRole('link', {
        name: locale === 'zh-Hans' ? /审阅权限/ : /審閱權限/,
      });
      await expect(button).toBeVisible();
      // Visible text is the short form; the full phrase lives in the label.
      await expect(button).toHaveText(locale === 'zh-Hans' ? '审阅' : '審閱');
    });

    test(`${locale} follow-up copy renders`, async ({ page }) => {
      await installLangBotApiMocks(page, {
        authenticated: true,
        language: locale,
      });
      const dialog = await shoot(page, 'multi', locale);

      for (const text of expected) {
        await expect(dialog.getByRole('link', { name: text })).toBeVisible();
      }
      // The pipeline step stays a single link in Chinese too.
      await expect(
        dialog.getByRole('link', { name: /流水[线線]/ }),
      ).toHaveCount(1);
    });
  }
});

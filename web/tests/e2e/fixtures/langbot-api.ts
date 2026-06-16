import { Page, Route } from '@playwright/test';

type JsonRecord = Record<string, unknown>;

interface SkillMock {
  name: string;
  display_name: string;
  description: string;
  instructions: string;
  package_root: string;
  updated_at: string;
}

interface LangBotApiMockState {
  skills: SkillMock[];
}

function ok(data: unknown) {
  return {
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  };
}

async function fulfillJson(route: Route, data: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(ok(data)),
  });
}

function routePath(route: Route) {
  return new URL(route.request().url()).pathname;
}

function emptyMonitoringData() {
  return {
    overview: {
      total_messages: 0,
      llm_calls: 0,
      embedding_calls: 0,
      model_calls: 0,
      success_rate: 0,
      active_sessions: 0,
    },
    messages: [],
    llmCalls: [],
    embeddingCalls: [],
    sessions: [],
    errors: [],
    totalCount: {
      messages: 0,
      llmCalls: 0,
      embeddingCalls: 0,
      sessions: 0,
      errors: 0,
    },
  };
}

function emptyTokenStatistics() {
  return {
    summary: {
      total_calls: 0,
      success_calls: 0,
      error_calls: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_tokens: 0,
      total_cost: 0,
      avg_tokens_per_call: 0,
      avg_duration_ms: 0,
      avg_tokens_per_second: 0,
      zero_token_success_calls: 0,
    },
    by_model: [],
    timeseries: [],
    bucket: 'day',
  };
}

function makeSkill(data: JsonRecord): SkillMock {
  return {
    name: String(data.name || ''),
    display_name: String(data.display_name || ''),
    description: String(data.description || ''),
    instructions: String(data.instructions || ''),
    package_root: String(data.package_root || ''),
    updated_at: new Date().toISOString(),
  };
}

async function handleBackendApi(route: Route, state: LangBotApiMockState) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname;
  const method = request.method();

  if (path === '/api/v1/system/info') {
    return fulfillJson(route, {
      debug: false,
      version: 'frontend-smoke',
      edition: 'community',
      cloud_service_url: 'https://space.langbot.app',
      enable_marketplace: true,
      allow_modify_login_info: true,
      disable_models_service: false,
      limitation: {
        max_bots: -1,
        max_pipelines: -1,
        max_extensions: -1,
      },
      outbound_ips: [],
      wizard_status: 'completed',
      wizard_progress: null,
    });
  }

  if (path === '/api/v1/user/account-info') {
    return fulfillJson(route, {
      initialized: true,
      account_type: 'local',
      has_password: true,
    });
  }

  if (path === '/api/v1/user/check-token') {
    return fulfillJson(route, { token: '' });
  }

  if (path === '/api/v1/user/auth') {
    return fulfillJson(route, { token: 'playwright-token' });
  }

  if (path === '/api/v1/user/info') {
    return fulfillJson(route, {
      user: 'admin@example.com',
      account_type: 'local',
      has_password: true,
    });
  }

  if (path === '/api/v1/user/space-credits') {
    return fulfillJson(route, { credits: null });
  }

  if (path === '/api/v1/platform/bots') {
    return fulfillJson(route, { bots: [] });
  }

  if (path === '/api/v1/pipelines') {
    return fulfillJson(route, { pipelines: [] });
  }

  if (path === '/api/v1/knowledge/bases') {
    return fulfillJson(route, { bases: [] });
  }

  if (path === '/api/v1/knowledge/migration/status') {
    return fulfillJson(route, {
      needed: false,
      internal_kb_count: 0,
      external_kb_count: 0,
    });
  }

  if (path === '/api/v1/plugins') {
    return fulfillJson(route, { plugins: [] });
  }

  if (path === '/api/v1/extensions') {
    return fulfillJson(route, { extensions: [] });
  }

  if (path === '/api/v1/mcp/servers') {
    return fulfillJson(route, { servers: [] });
  }

  if (path === '/api/v1/skills') {
    if (method === 'POST') {
      const skill = makeSkill(
        JSON.parse(request.postData() || '{}') as JsonRecord,
      );
      state.skills = [
        ...state.skills.filter((item) => item.name !== skill.name),
        skill,
      ];
      return fulfillJson(route, { skill });
    }

    return fulfillJson(route, { skills: state.skills });
  }

  const skillFileMatch = path.match(
    /^\/api\/v1\/skills\/([^/]+)\/files\/(.+)$/,
  );
  if (skillFileMatch) {
    const skillName = decodeURIComponent(skillFileMatch[1]);
    const filePath = decodeURIComponent(skillFileMatch[2]);
    const skill = state.skills.find((item) => item.name === skillName);
    return fulfillJson(route, {
      skill: { name: skillName },
      path: filePath,
      content: skill?.instructions || '',
    });
  }

  const skillFilesMatch = path.match(/^\/api\/v1\/skills\/([^/]+)\/files$/);
  if (skillFilesMatch) {
    const skillName = decodeURIComponent(skillFilesMatch[1]);
    return fulfillJson(route, {
      skill: { name: skillName },
      base_path: '.',
      entries: [
        {
          path: 'SKILL.md',
          name: 'SKILL.md',
          is_dir: false,
          size: null,
        },
      ],
      truncated: false,
    });
  }

  const skillMatch = path.match(/^\/api\/v1\/skills\/([^/]+)$/);
  if (skillMatch) {
    const skillName = decodeURIComponent(skillMatch[1]);
    const skill = state.skills.find((item) => item.name === skillName) || {
      name: skillName,
      display_name: '',
      description: '',
      instructions: '',
      package_root: '',
      updated_at: new Date().toISOString(),
    };
    return fulfillJson(route, { skill });
  }

  if (path === '/api/v1/system/status/plugin-system') {
    return fulfillJson(route, {
      is_enable: true,
      is_connected: true,
      plugin_connector_error: '',
    });
  }

  if (path === '/api/v1/plugins/debug-info') {
    return fulfillJson(route, {
      debug_url: 'ws://127.0.0.1:5300/plugin/debug',
      plugin_debug_key: 'test-debug-key',
    });
  }

  if (path === '/api/v1/box/status') {
    return fulfillJson(route, {
      available: true,
      enabled: true,
      profile: 'playwright',
      recent_error_count: 0,
      active_sessions: 0,
      managed_processes: 0,
      session_ttl_sec: 3600,
      backend: {
        name: 'playwright',
        available: true,
      },
    });
  }

  if (path === '/api/v1/box/sessions') {
    return fulfillJson(route, []);
  }

  if (path === '/api/v1/monitoring/data') {
    return fulfillJson(route, emptyMonitoringData());
  }

  if (path === '/api/v1/monitoring/overview') {
    return fulfillJson(route, emptyMonitoringData().overview);
  }

  if (path === '/api/v1/monitoring/token-statistics') {
    return fulfillJson(route, emptyTokenStatistics());
  }

  if (path === '/api/v1/monitoring/feedback/stats') {
    return fulfillJson(route, {
      total_feedback: 0,
      total_likes: 0,
      total_dislikes: 0,
      satisfaction_rate: 0,
    });
  }

  if (path === '/api/v1/monitoring/feedback') {
    return fulfillJson(route, { feedback: [], total: 0 });
  }

  if (path === '/api/v1/survey/pending') {
    return fulfillJson(route, { survey: null });
  }

  if (path === '/api/v1/system/tasks') {
    return fulfillJson(route, { tasks: [] });
  }

  if (
    path === '/api/v1/marketplace/plugins' ||
    path === '/api/v1/marketplace/plugins/search' ||
    path === '/api/v1/marketplace/extensions/search' ||
    path === '/api/v1/marketplace/mcps/search' ||
    path === '/api/v1/marketplace/skills/search'
  ) {
    return fulfillJson(route, { plugins: [], total: 0 });
  }

  if (path === '/api/v1/marketplace/tags') {
    return fulfillJson(route, { tags: [] });
  }

  if (path === '/api/v1/marketplace/recommendation-lists') {
    return fulfillJson(route, { lists: [] });
  }

  if (path === '/api/v1/dist/info/releases') {
    return fulfillJson(route, []);
  }

  if (path === '/api/v1/dist/info/repo') {
    return fulfillJson(route, {
      repo: {
        stargazers_count: 0,
        forks_count: 0,
        open_issues_count: 0,
      },
      contributors: [],
    });
  }

  await fulfillJson(route, {});
}

async function handleCloudApi(route: Route) {
  const path = routePath(route);

  if (
    path === '/api/v1/marketplace/plugins' ||
    path === '/api/v1/marketplace/plugins/search' ||
    path === '/api/v1/marketplace/extensions/search' ||
    path === '/api/v1/marketplace/mcps/search' ||
    path === '/api/v1/marketplace/skills/search'
  ) {
    return fulfillJson(route, { plugins: [], total: 0 });
  }

  if (path === '/api/v1/marketplace/tags') {
    return fulfillJson(route, { tags: [] });
  }

  if (path === '/api/v1/marketplace/recommendation-lists') {
    return fulfillJson(route, { lists: [] });
  }

  if (path === '/api/v1/dist/info/releases') {
    return fulfillJson(route, []);
  }

  if (path === '/api/v1/dist/info/repo') {
    return fulfillJson(route, {
      repo: {
        stargazers_count: 0,
        forks_count: 0,
        open_issues_count: 0,
      },
      contributors: [],
    });
  }

  await fulfillJson(route, {});
}

export async function installLangBotApiMocks(
  page: Page,
  options: { authenticated?: boolean; storage?: JsonRecord } = {},
) {
  const { authenticated = false, storage = {} } = options;
  const state: LangBotApiMockState = {
    skills: [],
  };

  await page.addInitScript(
    ({ authenticated, storage }) => {
      localStorage.setItem('langbot_language', 'en-US');
      localStorage.setItem('extensions_group_by_type', 'false');

      if (authenticated) {
        localStorage.setItem('token', 'playwright-token');
        localStorage.setItem('userEmail', 'admin@example.com');
      } else {
        localStorage.removeItem('token');
        localStorage.removeItem('userEmail');
      }

      for (const [key, value] of Object.entries(storage)) {
        localStorage.setItem(key, String(value));
      }
    },
    { authenticated, storage },
  );

  await page.route('**/api/v1/**', (route) => handleBackendApi(route, state));
  await page.route('https://space.langbot.app/**', handleCloudApi);
}

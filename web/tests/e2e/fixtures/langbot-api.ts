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

interface PipelineMock {
  uuid: string;
  name: string;
  description: string;
  config: JsonRecord;
  emoji: string;
  is_default: boolean;
  updated_at: string;
}

interface KnowledgeBaseMock {
  uuid: string;
  name: string;
  description: string;
  emoji: string;
  knowledge_engine_plugin_id: string;
  creation_settings: JsonRecord;
  retrieval_settings: JsonRecord;
  knowledge_engine: {
    plugin_id: string;
    name: {
      en_US: string;
      zh_Hans: string;
    };
    capabilities: string[];
  };
  updated_at: string;
}

interface MCPServerMock {
  name: string;
  mode: 'sse' | 'stdio' | 'http';
  enable: boolean;
  extra_args: JsonRecord;
  runtime_info: {
    status: 'connected';
    tool_count: number;
    tools: unknown[];
  };
  readme: string;
  updated_at: string;
}

interface BotMock {
  uuid: string;
  name: string;
  description: string;
  enable: boolean;
  adapter: string;
  adapter_config: JsonRecord;
  use_pipeline_uuid?: string;
  pipeline_routing_rules: unknown[];
  adapter_runtime_values: JsonRecord;
  updated_at: string;
}

export interface WorkspaceEntryMock {
  workspace: {
    uuid: string;
    instance_uuid: string;
    name: string;
    slug: string;
    type: 'personal' | 'team';
    status: 'active';
    source: 'local' | 'cloud_projection';
  };
  membership: {
    uuid: string;
    workspace_uuid: string;
    account_uuid: string;
    email: string;
    role: 'owner' | 'admin' | 'developer' | 'operator' | 'viewer';
    status: 'active';
    joined_at: string;
    created_at: string;
  };
  permissions: string[];
  placement_generation: number;
}

interface LangBotApiMockState {
  authenticated: boolean;
  bots: BotMock[];
  counters: Record<string, number>;
  knowledgeBases: KnowledgeBaseMock[];
  mcpServers: MCPServerMock[];
  monitoringData: unknown;
  monitoringSessions: unknown[];
  pipelines: PipelineMock[];
  sessionAnalyses: Record<string, unknown>;
  sessionMessages: Record<string, unknown[]>;
  skills: SkillMock[];
  workspaces: WorkspaceEntryMock[];
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

function parseJsonBody(route: Route): JsonRecord {
  return JSON.parse(route.request().postData() || '{}') as JsonRecord;
}

function now() {
  return new Date().toISOString();
}

export function makeWorkspaceEntry(
  uuid: string,
  name: string,
  source: 'local' | 'cloud_projection' = 'cloud_projection',
): WorkspaceEntryMock {
  const createdAt = now();
  return {
    workspace: {
      uuid,
      instance_uuid: 'instance-playwright',
      name,
      slug: uuid,
      type: 'team',
      status: 'active',
      source,
    },
    membership: {
      uuid: `membership-${uuid}`,
      workspace_uuid: uuid,
      account_uuid: 'account-playwright',
      email: 'admin@example.com',
      role: 'owner',
      status: 'active',
      joined_at: createdAt,
      created_at: createdAt,
    },
    permissions: [
      'api_key.manage',
      'audit.view',
      'member.invite',
      'member.remove',
      'member.update_role',
      'member.view',
      'owner.transfer',
      'provider_secret.manage',
      'resource.manage',
      'resource.view',
      'runtime.operate',
      'workspace.view',
    ],
    placement_generation: 1,
  };
}

function defaultWorkspaceEntry(): WorkspaceEntryMock {
  return makeWorkspaceEntry(
    'workspace-playwright',
    'Playwright Workspace',
    'local',
  );
}

function nextId(state: LangBotApiMockState, prefix: string) {
  state.counters[prefix] = (state.counters[prefix] || 0) + 1;
  return `${prefix}-${state.counters[prefix]}`;
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
    toolCalls: [],
    embeddingCalls: [],
    sessions: [],
    errors: [],
    totalCount: {
      messages: 0,
      llmCalls: 0,
      toolCalls: 0,
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

function makePipeline(
  state: LangBotApiMockState,
  data: JsonRecord,
  uuid = nextId(state, 'pipeline'),
): PipelineMock {
  return {
    uuid,
    name: String(data.name || ''),
    description: String(data.description || ''),
    config: (data.config as JsonRecord | undefined) || {
      ai: {},
      trigger: {},
      safety: {},
      output: {},
    },
    emoji: String(data.emoji || '⚙️'),
    is_default: false,
    updated_at: now(),
  };
}

function pipelineMetadata() {
  return {
    configs: [
      {
        name: 'ai',
        label: {
          en_US: 'AI Capabilities',
          zh_Hans: 'AI 能力',
        },
        stages: [
          {
            name: 'runner',
            label: {
              en_US: 'Runtime',
              zh_Hans: '运行方式',
            },
            config: [
              {
                id: 'runner',
                name: 'runner',
                label: {
                  en_US: 'Runner',
                  zh_Hans: '运行器',
                },
                type: 'select',
                required: true,
                default: 'local-agent',
                options: [
                  {
                    name: 'local-agent',
                    label: {
                      en_US: 'Built-in Agent',
                      zh_Hans: '内置 Agent',
                    },
                  },
                ],
              },
            ],
          },
          {
            name: 'local-agent',
            label: {
              en_US: 'Built-in Agent',
              zh_Hans: '内置 Agent',
            },
            config: [
              {
                id: 'model',
                name: 'model',
                label: {
                  en_US: 'Model',
                  zh_Hans: '模型',
                },
                type: 'model-fallback-selector',
                required: true,
                default: {
                  primary: 'llm-valid',
                  fallbacks: [],
                },
              },
            ],
          },
        ],
      },
    ],
  };
}

function providerModelList() {
  return {
    models: [
      {
        uuid: '',
        name: 'Broken Empty UUID Model',
        provider_uuid: 'provider-empty',
        provider: {
          uuid: 'provider-empty',
          name: 'Broken Provider',
          requester: 'mock-provider',
        },
      },
      {
        uuid: 'llm-valid',
        name: 'Valid Mock Model',
        provider_uuid: 'provider-valid',
        provider: {
          uuid: 'provider-valid',
          name: 'Mock Provider',
          requester: 'mock-provider',
        },
        abilities: ['func_call'],
      },
    ],
  };
}

function knowledgeEngine() {
  return {
    plugin_id: 'builtin/minimal-knowledge',
    name: {
      en_US: 'Minimal Knowledge Engine',
      zh_Hans: '最小知识库引擎',
    },
    description: {
      en_US: 'Minimal mocked engine for frontend smoke tests.',
      zh_Hans: '用于前端冒烟测试的最小模拟引擎。',
    },
    capabilities: ['text_retrieval'],
    creation_schema: [],
    retrieval_schema: [],
  };
}

function makeKnowledgeBase(
  state: LangBotApiMockState,
  data: JsonRecord,
  uuid = nextId(state, 'knowledge'),
): KnowledgeBaseMock {
  const engine = knowledgeEngine();
  return {
    uuid,
    name: String(data.name || ''),
    description: String(data.description || ''),
    emoji: String(data.emoji || '📚'),
    knowledge_engine_plugin_id: String(
      data.knowledge_engine_plugin_id || engine.plugin_id,
    ),
    creation_settings: (data.creation_settings as JsonRecord | undefined) || {},
    retrieval_settings:
      (data.retrieval_settings as JsonRecord | undefined) || {},
    knowledge_engine: {
      plugin_id: engine.plugin_id,
      name: engine.name,
      capabilities: engine.capabilities,
    },
    updated_at: now(),
  };
}

function makeMCPServer(data: JsonRecord): MCPServerMock {
  return {
    name: String(data.name || ''),
    mode: (data.mode as MCPServerMock['mode']) || 'sse',
    enable: data.enable !== false,
    extra_args: (data.extra_args as JsonRecord | undefined) || {},
    runtime_info: {
      status: 'connected',
      tool_count: 0,
      tools: [],
    },
    readme: '',
    updated_at: now(),
  };
}

function makeBot(
  state: LangBotApiMockState,
  data: JsonRecord,
  uuid = nextId(state, 'bot'),
): BotMock {
  return {
    uuid,
    name: String(data.name || ''),
    description: String(data.description || ''),
    enable: data.enable !== false,
    adapter: String(data.adapter || 'playwright-adapter'),
    adapter_config: (data.adapter_config as JsonRecord | undefined) || {},
    use_pipeline_uuid: data.use_pipeline_uuid
      ? String(data.use_pipeline_uuid)
      : undefined,
    pipeline_routing_rules:
      (data.pipeline_routing_rules as unknown[] | undefined) || [],
    adapter_runtime_values: {
      webhook_full_url: `https://playwright.test/bots/${uuid}/webhook`,
      extra_webhook_full_url: '',
    },
    updated_at: now(),
  };
}

function mockAdapters() {
  return [
    {
      name: 'playwright-adapter',
      label: {
        en_US: 'Playwright Adapter',
        zh_Hans: 'Playwright 适配器',
      },
      description: {
        en_US: 'Minimal adapter for frontend E2E tests.',
        zh_Hans: '用于前端 E2E 测试的最小适配器。',
      },
      spec: {
        categories: ['testing'],
        config: [],
      },
    },
  ];
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
      password_login_enabled: true,
      space_login_enabled: false,
    });
  }

  if (path === '/api/v1/user/check-token') {
    return fulfillJson(route, {
      token: state.authenticated ? 'playwright-token' : '',
    });
  }

  if (path === '/api/v1/user/auth') {
    state.authenticated = true;
    return fulfillJson(route, { token: 'playwright-token' });
  }

  if (path === '/api/v1/user/space/callback') {
    state.authenticated = true;
    return fulfillJson(route, {
      token: 'playwright-space-token',
      user: 'admin@example.com',
    });
  }

  if (path === '/api/v1/user/info') {
    return fulfillJson(route, {
      account_uuid: 'account-playwright',
      user: 'admin@example.com',
      account_type: 'local',
      has_password: true,
    });
  }

  if (path === '/api/v1/user/space-credits') {
    return fulfillJson(route, { credits: null });
  }

  if (path === '/api/v1/workspaces/bootstrap') {
    return fulfillJson(route, { workspaces: state.workspaces });
  }

  if (path === '/api/v1/workspaces/current') {
    const selectedWorkspaceUuid = request.headers()['x-workspace-id'];
    const entry = state.workspaces.find(
      (item) => item.workspace.uuid === selectedWorkspaceUuid,
    );
    return fulfillJson(route, entry || state.workspaces[0]);
  }

  if (path === '/api/v1/workspaces') {
    return fulfillJson(route, {
      workspaces: state.workspaces.map((entry) => entry.workspace),
    });
  }

  if (path === '/api/v1/platform/adapters') {
    return fulfillJson(route, { adapters: mockAdapters() });
  }

  if (path === '/api/v1/platform/bots') {
    if (method === 'POST') {
      const bot = makeBot(state, parseJsonBody(route));
      state.bots = [
        ...state.bots.filter((item) => item.uuid !== bot.uuid),
        bot,
      ];
      return fulfillJson(route, { uuid: bot.uuid });
    }

    return fulfillJson(route, { bots: state.bots });
  }

  const botLogsMatch = path.match(/^\/api\/v1\/platform\/bots\/([^/]+)\/logs$/);
  if (botLogsMatch) {
    return fulfillJson(route, { logs: [], total: 0 });
  }

  const botMatch = path.match(/^\/api\/v1\/platform\/bots\/([^/]+)$/);
  if (botMatch) {
    const botId = decodeURIComponent(botMatch[1]);

    if (method === 'PUT') {
      const bot = makeBot(state, parseJsonBody(route), botId);
      state.bots = [...state.bots.filter((item) => item.uuid !== botId), bot];
      return fulfillJson(route, {});
    }

    if (method === 'DELETE') {
      state.bots = state.bots.filter((item) => item.uuid !== botId);
      return fulfillJson(route, {});
    }

    const bot = state.bots.find((item) => item.uuid === botId);
    return fulfillJson(route, {
      bot: bot || makeBot(state, { name: botId }, botId),
    });
  }

  if (path === '/api/v1/provider/models/llm') {
    return fulfillJson(route, providerModelList());
  }

  if (path === '/api/v1/provider/models/embedding') {
    return fulfillJson(route, { models: [] });
  }

  if (path === '/api/v1/provider/models/rerank') {
    return fulfillJson(route, { models: [] });
  }

  if (path === '/api/v1/pipelines/_/metadata') {
    return fulfillJson(route, pipelineMetadata());
  }

  if (path === '/api/v1/pipelines') {
    if (method === 'POST') {
      const pipeline = makePipeline(state, parseJsonBody(route));
      state.pipelines = [
        ...state.pipelines.filter((item) => item.uuid !== pipeline.uuid),
        pipeline,
      ];
      return fulfillJson(route, { uuid: pipeline.uuid });
    }

    return fulfillJson(route, { pipelines: state.pipelines });
  }

  const pipelineMatch = path.match(/^\/api\/v1\/pipelines\/([^/]+)$/);
  if (pipelineMatch) {
    const pipelineId = decodeURIComponent(pipelineMatch[1]);

    if (method === 'PUT') {
      const pipeline = makePipeline(state, parseJsonBody(route), pipelineId);
      state.pipelines = [
        ...state.pipelines.filter((item) => item.uuid !== pipelineId),
        pipeline,
      ];
      return fulfillJson(route, {});
    }

    if (method === 'DELETE') {
      state.pipelines = state.pipelines.filter(
        (item) => item.uuid !== pipelineId,
      );
      return fulfillJson(route, {});
    }

    const pipeline = state.pipelines.find((item) => item.uuid === pipelineId);
    return fulfillJson(route, {
      pipeline:
        pipeline || makePipeline(state, { name: pipelineId }, pipelineId),
    });
  }

  const pipelineExtensionsMatch = path.match(
    /^\/api\/v1\/pipelines\/([^/]+)\/extensions$/,
  );
  if (pipelineExtensionsMatch) {
    return fulfillJson(route, {
      enable_all_plugins: true,
      enable_all_mcp_servers: true,
      enable_all_skills: true,
      bound_plugins: [],
      available_plugins: [],
      bound_mcp_servers: [],
      available_mcp_servers: state.mcpServers,
      bound_skills: [],
      available_skills: state.skills,
    });
  }

  if (path === '/api/v1/knowledge/bases') {
    if (method === 'POST') {
      const base = makeKnowledgeBase(state, parseJsonBody(route));
      state.knowledgeBases = [
        ...state.knowledgeBases.filter((item) => item.uuid !== base.uuid),
        base,
      ];
      return fulfillJson(route, { uuid: base.uuid });
    }

    return fulfillJson(route, { bases: state.knowledgeBases });
  }

  const knowledgeBaseFilesMatch = path.match(
    /^\/api\/v1\/knowledge\/bases\/([^/]+)\/files$/,
  );
  if (knowledgeBaseFilesMatch) {
    return fulfillJson(route, { files: [] });
  }

  const knowledgeBaseMatch = path.match(
    /^\/api\/v1\/knowledge\/bases\/([^/]+)$/,
  );
  if (knowledgeBaseMatch) {
    const baseId = decodeURIComponent(knowledgeBaseMatch[1]);

    if (method === 'PUT') {
      const base = makeKnowledgeBase(state, parseJsonBody(route), baseId);
      state.knowledgeBases = [
        ...state.knowledgeBases.filter((item) => item.uuid !== baseId),
        base,
      ];
      return fulfillJson(route, { uuid: base.uuid });
    }

    if (method === 'DELETE') {
      state.knowledgeBases = state.knowledgeBases.filter(
        (item) => item.uuid !== baseId,
      );
      return fulfillJson(route, {});
    }

    const base = state.knowledgeBases.find((item) => item.uuid === baseId);
    return fulfillJson(route, {
      base: base || makeKnowledgeBase(state, { name: baseId }, baseId),
    });
  }

  if (path === '/api/v1/knowledge/engines') {
    return fulfillJson(route, { engines: [knowledgeEngine()] });
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
    if (method === 'POST') {
      const server = makeMCPServer(parseJsonBody(route));
      state.mcpServers = [
        ...state.mcpServers.filter((item) => item.name !== server.name),
        server,
      ];
      return fulfillJson(route, { task_id: nextId(state, 'task') });
    }

    return fulfillJson(route, { servers: state.mcpServers });
  }

  const mcpTestMatch = path.match(/^\/api\/v1\/mcp\/servers\/([^/]+)\/test$/);
  if (mcpTestMatch) {
    return fulfillJson(route, {
      runtime_info: {
        status: 'connected',
        tool_count: 0,
        tools: [],
      },
    });
  }

  const mcpServerMatch = path.match(/^\/api\/v1\/mcp\/servers\/([^/]+)$/);
  if (mcpServerMatch) {
    const serverName = decodeURIComponent(mcpServerMatch[1]);

    if (method === 'PUT') {
      const existing = state.mcpServers.find(
        (item) => item.name === serverName,
      );
      const server = makeMCPServer({
        ...(existing || {}),
        ...parseJsonBody(route),
        name: serverName,
      });
      state.mcpServers = [
        ...state.mcpServers.filter((item) => item.name !== serverName),
        server,
      ];
      return fulfillJson(route, { task_id: nextId(state, 'task') });
    }

    if (method === 'DELETE') {
      state.mcpServers = state.mcpServers.filter(
        (item) => item.name !== serverName,
      );
      return fulfillJson(route, { task_id: nextId(state, 'task') });
    }

    const server = state.mcpServers.find((item) => item.name === serverName);
    return fulfillJson(route, {
      server: server || makeMCPServer({ name: serverName }),
    });
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
    if (method === 'PUT') {
      const skill = makeSkill({
        ...parseJsonBody(route),
        name: skillName,
      });
      state.skills = [
        ...state.skills.filter((item) => item.name !== skillName),
        skill,
      ];
      return fulfillJson(route, { skill });
    }

    if (method === 'DELETE') {
      state.skills = state.skills.filter((item) => item.name !== skillName);
      return fulfillJson(route, {});
    }

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
    return fulfillJson(route, state.monitoringData);
  }

  if (path === '/api/v1/monitoring/sessions') {
    return fulfillJson(route, {
      sessions: state.monitoringSessions,
      total: state.monitoringSessions.length,
    });
  }

  if (path === '/api/v1/monitoring/messages') {
    const sessionId = url.searchParams.get('sessionId') || '';
    const messages = state.sessionMessages[sessionId] || [];
    return fulfillJson(route, {
      messages,
      total: messages.length,
    });
  }

  const sessionAnalysisMatch = path.match(
    /^\/api\/v1\/monitoring\/sessions\/([^/]+)\/analysis$/,
  );
  if (sessionAnalysisMatch) {
    const sessionId = decodeURIComponent(sessionAnalysisMatch[1]);
    return fulfillJson(
      route,
      state.sessionAnalyses[sessionId] || {
        session_id: sessionId,
        found: true,
        tool_calls: [],
      },
    );
  }

  if (path === '/api/v1/monitoring/overview') {
    const data = state.monitoringData as { overview?: unknown };
    return fulfillJson(route, data.overview || emptyMonitoringData().overview);
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
  options: {
    authenticated?: boolean;
    monitoringData?: unknown;
    monitoringSessions?: unknown[];
    sessionAnalyses?: Record<string, unknown>;
    sessionMessages?: Record<string, unknown[]>;
    storage?: JsonRecord;
    workspaces?: WorkspaceEntryMock[];
  } = {},
) {
  const {
    authenticated = false,
    monitoringData,
    monitoringSessions,
    sessionAnalyses,
    sessionMessages,
    storage = {},
    workspaces = [defaultWorkspaceEntry()],
  } = options;
  const state: LangBotApiMockState = {
    authenticated,
    bots: [],
    counters: {},
    knowledgeBases: [],
    mcpServers: [],
    monitoringData: monitoringData || emptyMonitoringData(),
    monitoringSessions: monitoringSessions || [],
    pipelines: [],
    sessionAnalyses: sessionAnalyses || {},
    sessionMessages: sessionMessages || {},
    skills: [],
    workspaces,
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

# 单元测试覆盖率排除说明

## 排除范围

以下外部适配器模块不纳入测试覆盖目标，因为它们需要实际外部环境才能测试：

### 1. 消息平台适配器 (`platform/sources/`)
- **路径**: `src/langbot/pkg/platform/sources/`
- **模块**: aiocqhttp, dingtalk, discord, feishu, gestep, kook, lark, slack, telegram, wecom, wechatpv, wechatmp, qqbot
- **排除原因**: 需要真实消息平台账号和 webhook 连接，无法纯单元测试
- **测试方式**: 需要 mock 平台 API 或集成测试环境
- **状态**: 后续可补充 mock 测试

### 2. LLM Requester (`provider/modelmgr/requesters/`)
- **路径**: `src/langbot/pkg/provider/modelmgr/requesters/`
- **模块**: deepseek, openai, anthropic, gemini, moonshot, ollama, zhipuai 等 20+ 个 requester
- **排除原因**: 需要真实 LLM API 密钥和网络请求，涉及付费 API 调用
- **测试方式**: 需要 mock HTTP 响应或使用 fake LLM server
- **状态**: 后续可补充 mock HTTP 测试

### 3. Agent Runner (`provider/runners/`)
- **路径**: `src/langbot/pkg/provider/runners/`
- **模块**: cozeapi, difysvapi, n8nsvapi, langflowapi, dashscopeapi, localagent, tboxapi
- **排除原因**: 需要真实 Agent 平台（Coze、Dify、n8n 等）的 API 连接
- **测试方式**: 需要 mock Agent 平台响应
- **状态**: 后续可补充 mock 测试

### 4. 向量数据库 (`vector/vdbs/`)
- **路径**: `src/langbot/pkg/vector/vdbs/`
- **模块**: chroma, milvus, pgvector, qdrant, seekdb
- **排除原因**: 需要真实向量数据库实例运行
- **测试方式**: 需要 Docker 启动测试数据库或 mock
- **状态**: 后续可补充 mock 测试

---

## 覆盖率计算（排除外部适配器）

### 统计方法

```bash
# 排除外部适配器后计算覆盖率
pytest tests/unit_tests/ --cov=langbot.pkg \
  --cov-fail-under=0 \
  -o "cov_exclude_patterns=platform/sources/*,provider/modelmgr/requesters/*,provider/runners/*,vector/vdbs/*"
```

### 当前覆盖率（排除后）

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| `command` | **99%** | ✅ 完成 |
| `entity` | **99%** | ✅ 完成 |
| `vector` | **76%** | ✅ 完成 |
| `survey` | **84%** | ✅ 完成 |
| `pipeline` | **72%** | ✅ 核心流程 |
| `rag` | **66%** | ✅ 完成 |
| `telemetry` | **87%** | ✅ 完成 |
| `storage` | **80%** | ✅ 完成 |
| `provider` | **83%** | ✅ 完成 |
| `discover` | **61%** | ✅ 完成 |
| `config` | **70%** | ✅ 完成 |
| `utils` | **48%** | 🔄 部分完成 |
| `api` | **34%** | 🔄 需补充 controller |
| `platform` | **35%** | 🔄 需补充 adapter base |
| `plugin` | **27%** | 🔄 需补充 handler |
| `core` | **28%** | 🔄 需补充 app 启动 |
| `persistence` | **24%** | 🔄 需补充 mgr |

---

## 后续计划

### 可补充的 Mock 测试（优先级排序）

1. **`provider/modelmgr/requesters/`** (优先级：中)
   - 使用 `httpx` mock 测试 API 响应解析
   - 测试重试逻辑、错误处理

2. **`provider/runners/`** (优先级：中)
   - Mock Agent 平台响应
   - 测试 session 管理、错误处理

3. **`platform/sources/`** (优先级：低)
   - Mock 平台 webhook 事件
   - 测试消息解析、事件处理

4. **`vector/vdbs/`** (优先级：低)
   - Mock 向量数据库操作
   - 测试 CRUD、查询逻辑

---

## 测试文件结构

```
tests/unit_tests/
├── api/
│   └── service/
│       ├── test_knowledge_service.py  # 22 tests ✅
│       └── ...
├── core/
│   ├── test_taskmgr.py                 # 21 tests ✅
│   ├── test_load_config.py             # 21 tests ✅ (含env override)
│   └── ...
├── plugin/
│   ├── test_connector_static.py        # 8 tests ✅
│   ├── test_connector_pure.py          # 7 tests ✅
│   ├── test_connector_methods.py       # 24 tests ✅
│   ├── test_extract_deps.py            # 7 tests ✅
│   ├── test_handler_actions.py         # 15 tests ✅ (新增)
│   └── ...
├── provider/
│   ├── test_session_manager.py         # 11 tests ✅ (新增)
│   ├── test_tool_manager.py            # 14 tests ✅ (新增)
│   └── ...
├── rag/
│   ├── test_i18n_conversion.py         # 8 tests ✅
│   ├── test_kbmgr.py                   # 39 tests ✅
│   ├── test_file_storage.py            # 21 tests ✅ (新增)
│   └── ...
├── storage/
│   ├── test_s3storage.py               # 16 tests ✅ (新增)
│   ├── test_localstorage_path_traversal.py # 11 tests ✅
│   └── ...
├── survey/
│   └── test_survey_manager.py          # 22 tests ✅
├── telemetry/
│   └── test_telemetry.py               # 25 tests ✅ (重写)
├── vector/
│   ├── test_filter_utils.py            # 21 tests ✅
│   ├── test_vdb_filter_conversion.py   # 30 tests ✅ (新增)
│   └── ...
├── utils/
│   ├── test_platform.py                # 7 tests ✅
│   ├── test_funcschema.py              # 9 tests ✅
│   └── ...
├── pipeline/
│   ├── test_ratelimit.py               # 12 tests ✅ (新增真实算法)
│   ├── test_msgtrun.py                 # 9 tests ✅ (强化断言)
│   └── ...
└── persistence/
    ├── test_serialize_model.py         # 6 tests ✅
    ├── test_database_decorator.py      # 7 tests ✅
    └── ...
```

---

## 总结

- **总测试数**: 1193 passed
- **总体覆盖率**: 30%
- **核心模块覆盖率**: **51.2%** (6549/12825 语句) - 排除外部适配器
- **外部适配器覆盖率**: 5.6% (535/9483 语句) - 不纳入目标

### 核心模块覆盖率详情

| 模块 | 覆盖率 | 语句数 | 说明 |
|------|--------|--------|------|
| `command` | **99%** | 93 | ✅ 完成 |
| `entity` | **99%** | 335 | ✅ 完成 |
| `vector` | **76%** | 139 | ✅ 完成 (新增filter转换测试) |
| `survey` | **84%** | 95 | ✅ 完成 |
| `pipeline` | **72%** | 1761 | ✅ 核心流程 (新增算法测试) |
| `rag` | **66%** | 347 | ✅ 完成 (新增ZIP处理测试) |
| `telemetry` | **87%** | 70 | ✅ 完成 (重写假测试) |
| `storage` | **80%** | 170 | ✅ 完成 (新增S3测试) |
| `provider` | **83%** | 854 | ✅ 完成 (新增Session/Tool测试) |
| `discover` | **61%** | 188 | ✅ 完成 |
| `config` | **70%** | 198 | ✅ 完成 |
| `utils` | **48%** | 478 | 🔄 部分完成 |
| `api` | **34%** | 4061 | 🔄 需补充 controller |
| `platform` | **35%** | 433 | 🔄 需补充 adapter base |
| `plugin` | **27%** | 815 | 🔄 需补充 handler (新增action测试) |
| `core` | **28%** | 1289 | 🔄 需补充 app 启动 |
| `persistence` | **24%** | 1099 | 🔄 需补充 mgr |

外部适配器测试需要 mock 环境或集成测试，不属于纯单元测试范畴。
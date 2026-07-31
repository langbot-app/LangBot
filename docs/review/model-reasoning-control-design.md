# 模型思考控制设计方案

> 日期：2026-07-31
> 状态：Phase 1 已审核并实现
> 范围：LangBot 主仓库的模型配置、LiteLLM 请求层、Local Agent、Web 管理面板、监控与测试

## 1. 结论

建议为 LangBot 增加一套与厂商参数解耦的“思考策略”模型，并明确区分三个概念：

1. **思考能力**：模型是否支持思考，以及支持开关、档位还是 token 预算。
2. **思考策略**：一次请求选择厂商默认、关闭、开启或指定思考档位。
3. **思考展示**：是否把模型返回的思考内容展示给最终用户。

现有 `remove-think` 只属于第 3 类。它会过滤输出，但不会阻止模型思考，也不会降低思考 token、费用或延迟。新能力不应复用或改写这个字段。

推荐实现原则：

- 默认值为 `provider_default`，不向上游增加任何新参数，现有模型行为完全不变。
- 用户显式选择的策略必须被准确执行；无法准确执行时返回明确错误，不静默降级。
- LangBot 内部只保存统一策略，Provider 请求层负责翻译成各厂商参数。
- `extra_args` 保留为高级逃生口，但不能成为主 UI 的思考配置方式。
- 模型页只管理并展示能力；可写策略归属于 Local Agent 流水线，同一模型可在不同业务中使用不同思考量。
- 原始 reasoning 数据与展示文本分开保存，保证多轮对话、工具调用和签名字段不丢失。

## 2. 调研结论

### 2.1 可验证资料

本次结论基于以下可验证来源：

- OpenAI 官方 Reasoning Guide：`reasoning.effort` 的可选值由模型决定，可包括 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`；低档位偏向低延迟和低 token，高档位偏向质量。
  - https://developers.openai.com/api/docs/guides/reasoning#reasoning-effort
- LangBot 锁定的 LiteLLM `1.88.1` 实现。`uv.lock` 已锁定该版本，本地缓存中的适配代码可以确认 LangBot 实际依赖所支持的翻译行为。
- LangBot 当前实现：模型级 `extra_args` 会在 `LiteLLMRequester._build_completion_args()` 中直接合并到 `acompletion()` 参数。

Anthropic、Google 和 LiteLLM 的官方文档域名在本次环境中被浏览器策略禁止访问，因此下表中这些厂商的结论以 LiteLLM `1.88.1` 实际适配代码为准。实施前应再用对应厂商官方文档做一次参数范围核验，尤其是模型代际和允许值。

### 2.2 厂商差异矩阵

| Provider / 生态 | 可控制能力 | LiteLLM 1.88.1 统一入口 | 关键限制 | 建议支持级别 |
| --- | --- | --- | --- | --- |
| OpenAI | 思考档位，部分模型支持 `none` | `reasoning_effort` | 每个模型支持的档位不同，不能把 `none` 当成通用能力 | 首批完整支持 |
| Anthropic | 旧模型使用 extended thinking + token budget；新模型可用 adaptive thinking + effort | `reasoning_effort` 或 `thinking` | `none` 表示不发送 thinking；新旧模型的映射不同 | 首批完整支持 |
| Gemini | 2.x 主要映射为 `thinkingBudget`；3.x 主要映射为 `thinkingLevel` | `reasoning_effort` 或 `thinking` | Gemini 3 的 `none` 可能只能降到最低档，不能保证真正关闭 | 首批支持，但严格限制关闭语义 |
| DeepSeek | 开启/关闭；当前适配不支持预算档位 | `thinking={type: enabled}`；非 `none` effort 会映射成开启 | 多轮思考模式要求回传 `reasoning_content` | 首批开关支持 |
| xAI | 思考档位 | `reasoning_effort` | 仅 reasoning-capable 模型接受 | 首批完整支持 |
| Ollama | `think` 布尔值；部分模型接受 low/medium/high | `reasoning_effort` | 非 gpt-oss 模型的档位可能退化为布尔开关 | 首批支持，按模型能力裁剪 UI |
| OpenRouter | 聚合多厂商的 reasoning 参数 | `reasoning_effort`、`thinking` | 实际能力由路由后的模型决定 | 首批支持，能力未知时要求测试 |
| Volcengine / Doubao | `thinking.type` 支持 enabled/disabled/auto | LiteLLM `volcengine` 适配器支持 `thinking` | LangBot 当前 manifest 使用 `openai`，不会进入该适配器 | 第二批，先修正路由并回归 |
| Bailian / Qwen | 厂商兼容接口有独立思考开关/预算 | LiteLLM `dashscope` 适配器目前未提供统一 reasoning 映射 | LangBot 当前 manifest 使用 `openai`，只能通过高级参数透传 | 第二批，实施前核对官方字段 |
| 其他 OpenAI-compatible 网关 | 取决于网关 | 尝试标准 `reasoning_effort` | 不能仅凭模型名推断完整能力 | 保守支持，默认不自动开启 |

### 2.3 对 LangBot 的直接含义

不能把这个功能实现成单一 `enable_thinking: bool`，原因如下：

- 有的模型只有开关，有的模型只有档位，有的模型允许精确 token 预算。
- 有的模型本身始终推理，只能降低思考量，无法真正关闭。
- 同一个通用档位在不同厂商会映射成不同的实际预算。
- 聚合网关和自定义 OpenAI-compatible 服务无法可靠地通过模型名识别能力。
- “不展示思考内容”不等于“关闭思考”。

## 3. 当前项目现状

### 3.1 已有能力

- `LLMModel.extra_args` 是 JSON 字段，Web 端已有通用高级参数编辑器。
- `LiteLLMRequester` 会按“模型级 `extra_args`，再调用级 `extra_args`”的顺序合并参数。
- LiteLLM 已统一处理多个 Provider 的 `reasoning_effort`、`thinking` 和返回的 `reasoning_content`。
- `LocalAgentRunner` 的非流式、流式、工具调用和 fallback 路径都经过 `RuntimeProvider.invoke_llm*()`。
- `remove-think` 已能控制 `<think>` 或独立 reasoning 内容是否进入展示文本。
- Gemini 工具调用所需的 `provider_specific_fields` / thought signature 已有保留逻辑和单元测试。

### 3.2 现有缺口

- 管理员只能手写 `extra_args`，没有统一语义、能力提示和校验。
- `remove-think` 名称容易被误解为关闭模型思考。
- 模型扫描只识别 `vision` 和 `func_call`，没有 reasoning 能力。
- 当前返回处理会把 `reasoning_content` 拼进 `<think>` 文本后删除原字段，可能损失多轮思考所需的结构化数据。
- DeepSeek 思考模式需要在后续轮次回传 `reasoning_content`，当前链路不能保证完整保留。
- Pipeline 只能选择模型，不能针对业务覆盖模型的思考策略。
- 监控只记录总输入/输出 token，没有单独展示 reasoning token。
- 部分 Provider manifest 仍声明为通用 `openai`，导致 LiteLLM 的厂商专用翻译器不会生效。

### 3.3 预计改动地图

| 层 | 主要文件 | 责任 |
| --- | --- | --- |
| 持久化 | `src/langbot/pkg/entity/persistence/model.py`、`src/langbot/pkg/persistence/alembic/versions/` | 新增 `reasoning_config` JSON 列和 Alembic 迁移 |
| 模型服务 | `src/langbot/pkg/api/http/service/model.py` | CRUD 校验、冲突检测、测试模型时使用统一策略 |
| HTTP 控制器 | `src/langbot/pkg/api/http/controller/groups/provider/models.py` | 继续复用现有模型路由，不新增平行 API |
| 模型管理 | `src/langbot/pkg/provider/modelmgr/modelmgr.py` | 临时模型、数据库模型与扫描结果加载新字段 |
| 请求抽象 | `src/langbot/pkg/provider/modelmgr/requester.py` | 定义能力查询和 reasoning 参数构建接口 |
| LiteLLM 适配 | `src/langbot/pkg/provider/modelmgr/requesters/litellmchat.py` | 能力识别、策略翻译、参数合并、reasoning 返回保留 |
| Provider manifest | `src/langbot/pkg/provider/modelmgr/requesters/*.yaml` | 必要时修正 Provider 路由；相关变更放到独立阶段 |
| Agent 调用 | `src/langbot/pkg/provider/runners/localagent.py` | 所有非流式、流式、工具调用、fallback 路径传递统一策略 |
| Pipeline 元数据 | `src/langbot/templates/metadata/pipeline/ai.yaml` | 第二阶段加入 Pipeline 级覆盖 |
| 输出配置 | `src/langbot/templates/metadata/pipeline/output.yaml` | 保留键名，澄清 `remove-think` 只控制展示 |
| Web 类型/API | `web/src/app/infra/entities/api/index.ts`、`web/src/app/infra/http/BackendClient.ts` | 增加配置与能力响应类型 |
| 模型 UI | `web/src/app/home/components/models-dialog/` | 能力标记、策略控件、校验、模型测试 |
| i18n | `web/src/i18n/locales/` | 至少补齐英文、简体中文及项目已有覆盖语言 |
| 测试 | `tests/unit_tests/provider/`、`web/tests/` | 翻译、服务、流式 round-trip、前端状态测试 |

Phase 1 不修改 `langbot-plugin-sdk` 的公共实体或运行时协议。现有 `provider_message.Message.provider_specific_fields` 已可承载 Provider 原始 reasoning 数据；只有后续要把 reasoning 升级为跨插件公开实体时，才需要跨仓库 SDK 变更。

## 4. 领域模型

### 4.1 统一策略

新增 `ReasoningConfig`，保存于 LLM 模型，Pipeline 可提供同结构覆盖。产品层只暴露一个离散档位：

```json
{
  "level": "provider_default"
}
```

字段定义：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `level` | `provider_default \| disabled \| enabled \| minimal \| low \| medium \| high \| xhigh \| max` | 同时表达开关和思考强度 |

校验规则：

- `provider_default`：不发送任何 reasoning 参数，保持厂商和模型默认行为。
- `disabled`：明确关闭；仅当模型可真正关闭时允许保存/运行。
- `enabled`：明确开启，但由 Provider 决定具体强度，适用于只有开关的模型。
- `minimal` 到 `max`：明确开启，并指定强度；仅允许选择模型实际支持的档位。
- 厂商的 `auto` 统一映射为 `provider_default`，不再增加一个重复状态。
- 精确 token 预算不进入主数据结构。少数需要预算的场景继续通过高级参数配置，并由模型测试接口校验。

### 4.2 能力描述

沿用现有 `LLMModel.abilities`，新增 `reasoning` 能力标记。同时由后端在 API 返回中计算只读的 `reasoning_capabilities`：

```json
{
  "supported": true,
  "controls": ["toggle", "effort"],
  "efforts": ["none", "low", "medium", "high"],
  "can_disable": true,
  "source": "litellm"
}
```

设计约束：

- `abilities` 仍是用户可编辑的粗粒度能力，符合现有 `vision`、`func_call` 模式。
- `reasoning_capabilities` 不持久化，优先从 LiteLLM 模型元数据计算，避免模型升级后数据库残留过期能力。
- 无法识别的自定义模型返回 `supported: null`、`source: unknown`，不猜测。
- 用户可手动添加 `reasoning` ability，但未知能力模型必须先通过“测试模型”验证显式策略。
- UI 只展示后端声明可用的控件；未知模型保留 Provider Default 和高级参数入口。

### 4.3 持久化

在 `llm_models` 表新增 JSON 列：

```text
reasoning_config JSON NOT NULL DEFAULT {"level":"provider_default"}
```

使用 Alembic 新迁移，不修改冻结的 legacy migration。

该列作为已实现版本的兼容字段保留；新的模型页不再提供写入口，Local Agent 请求以流水线中按模型 UUID 保存的策略为准。

不建议把内部策略塞进 `extra_args`，原因是当前 `extra_args` 会原样发送给 LiteLLM；使用保留键会让内部元数据泄漏到上游，并使高级参数与产品配置难以区分。

## 5. 配置优先级与请求流程

### 5.1 优先级

```text
Pipeline 当前候选模型策略
        ↓ 缺少配置时固定为 provider_default
Provider / 模型默认行为
```

请求参数合并顺序：

```text
基础参数
  -> 模型 extra_args
  -> 调用级 extra_args
  -> 统一 reasoning 策略翻译结果（最后应用）
```

统一策略最后应用，可以确保流水线行为不受模型页历史设置影响。为了避免用户困惑，保存和测试时要检测 `extra_args` 中的冲突字段；当 `level != provider_default` 时，发现以下字段应直接报错：

- `reasoning_effort`
- `thinking`
- `reasoning`
- `extra_body` 内已知的 `thinking`、`enable_thinking`、`thinking_budget` 等字段

当 `level == provider_default` 时继续允许这些高级参数，保证旧配置兼容。

### 5.2 翻译层

在 `pkg/provider/modelmgr/` 内新增独立的 reasoning 规范化模块，职责是：

1. 读取当前流水线候选模型的请求级策略。
2. 查询 `ProviderAPIRequester.get_reasoning_capabilities(model)`。
3. 严格校验策略是否可以准确执行。
4. 生成 LiteLLM 参数，不直接发 HTTP。
5. 返回可观测的“最终生效策略”供日志和测试使用。

建议接口：

```python
class ProviderAPIRequester:
    def get_reasoning_capabilities(self, model: RuntimeLLMModel) -> ReasoningCapabilities: ...

    def build_reasoning_args(
        self,
        model: RuntimeLLMModel,
        config: ReasoningConfig,
    ) -> dict[str, Any]: ...
```

LiteLLMRequester 默认优先生成统一参数：

- 强度档位：`reasoning_effort=<level>`
- 仅开启：`thinking={"type":"enabled"}` 或 Provider 等价参数
- 关闭：优先 `reasoning_effort="none"`
- 高级参数中的精确预算：`thinking={"type":"enabled","budget_tokens":N}`

Provider 特例只放在 requester 翻译层，不进入 Pipeline 或平台适配器。

### 5.3 Provider 特例

- **Gemini 3**：如果 LiteLLM 能力表不能确认真正关闭，`disabled` 必须报“不支持关闭，可选择 Provider Default 或最低档”，不能把 `none` 静默映射成 low/minimal。
- **DeepSeek**：所有非 `none` 档位最终都只是开启。能力 API 只返回 `toggle`，UI 不显示档位；多轮必须保存并回传 `reasoning_content`。
- **Ollama**：仅对明确支持等级的模型展示 effort；其他模型只展示开关。
- **OpenRouter**：以路由后的模型能力为准。模型未知时允许 Provider Default，显式策略必须通过测试接口。
- **Volcengine**：使用 `thinking.type=enabled/disabled/auto`。应先让该 requester 进入 LiteLLM `volcengine` 适配器，或增加等价的明确翻译，不能依赖模型名。
- **Bailian/Qwen**：作为第二批 Provider 专用翻译。实施前核对官方字段、模型范围、预算上下限和流式返回结构，不凭经验写接口。

## 6. 返回数据与思考展示

### 6.1 保留原始 reasoning

当前 `LiteLLMRequester` 会读取 `reasoning_content`，将其拼接成 `<think>` 文本，再删除原字段。建议改为：

```text
上游 reasoning_content
  ├─ 原样保存在 Message.provider_specific_fields.reasoning_content
  └─ 根据 remove-think 决定是否渲染为 <think>...</think>
```

流式路径需要在 accumulator 中分别累计 `content` 与 `reasoning_content`，最终消息必须携带结构化 reasoning。不能只依赖已经渲染的 `<think>` 文本反向解析。

这样可以同时满足：

- `remove-think=true` 时用户看不到思考内容，但多轮协议仍能回传必要数据。
- `remove-think=false` 时保持当前用户体验。
- DeepSeek 多轮 thinking 不丢上下文。
- Gemini thought signature、Anthropic thinking block 等 Provider 字段可以继续按结构化方式 round-trip。

### 6.2 现有字段处理

保留数据库和 Pipeline 配置键 `remove-think`，避免破坏兼容。Web 文案改为更准确的：

- 中文：`向用户展示思考过程`
- 英文：`Show reasoning process`

UI 使用正向开关，保存时转换回 `remove-think = !showReasoning`。文案必须强调它只影响展示，不影响模型是否思考、token 或费用。

## 7. Web 管理面板

### 7.1 模型编辑

模型页只承担能力管理和只读展示：

1. `Reasoning` ability 复选框与 Vision、Function Calling 并列，供无法自动识别的自定义模型手动声明能力。
2. 模型卡片使用简短图标或 badge 标识 reasoning 能力。
3. 模型页不提供可写思考挡位，避免模型默认值与流水线策略形成两个控制源。

### 7.2 Local Agent 流水线策略

在 Local Agent 的主模型和每一个 fallback 模型下分别显示紧凑离散滑杆：

1. `Provider 默认` 始终为首个选项；选择它时不向上游增加任何思考参数。
2. 完整档位顺序为：`Provider 默认 / 关闭 / 开启 / 最低 / 低 / 中 / 高 / 极高 / 最大`。
3. 前端只渲染后端为该模型返回的可用档位；仅开关模型显示 `Provider 默认 / 关闭 / 开启`。
4. 模型不能真正关闭时不提供 `关闭`；能力未知时只显示不可调的 `Provider 默认`。
5. 主模型和 fallback 分别保存策略，切换候选模型时不会把一个模型的挡位错误应用到另一个模型。
6. Dify、Coze、Langflow、n8n 等外部 Runner 不显示该控件，因为 LangBot 不直接发起其内部模型请求。

流水线配置保持旧格式兼容，并在模型选择对象中增加按 UUID 保存的映射：

```json
{
  "model": {
    "primary": "primary-model-uuid",
    "fallbacks": ["fallback-model-uuid"],
    "reasoning": {
      "primary-model-uuid": "high"
    }
  }
}
```

`provider_default` 不写入映射；缺少 `reasoning` 的旧流水线天然等价于全部使用 Provider 默认。

滑杆交互要求：轨道使用现有主色和中性灰，不使用渐变；当前档位同时显示文字；支持键盘方向键和正确的 ARIA value text；窄屏下不溢出。

### 7.3 i18n

新增文案至少覆盖 `en_US`、`zh_Hans`；`ja_JP` 在模型面板现有同类字段已覆盖时同步补齐。不要把厂商参数名直接作为用户文案。

## 8. API、MCP 与 Skill

### 8.1 HTTP API

模型 CRUD 增加：

- 请求字段：`reasoning_config`
- 响应字段：`reasoning_config`
- 只读字段：`reasoning_capabilities`

模型测试接口必须使用与真实请求完全相同的规范化和翻译逻辑，并在失败时返回可操作错误，例如：

```text
Model gemini-3-... cannot disable reasoning.
Supported controls: effort=[low, medium, high].
```

可选增加只读调试信息，仅在测试接口返回：

```json
{
  "effective_reasoning": {
    "level": "low",
    "translated_keys": ["reasoning_effort"]
  }
}
```

不得返回 API key、完整请求正文或原始思考内容。

### 8.2 MCP 与技能

当前 MCP 仅列出模型 Provider，没有完整模型 CRUD 工具。如果本次不新增 agent-accessible HTTP 操作，则无需强行新增 MCP 工具。

如果后续让 Agent 修改模型思考策略，则必须同一提交更新：

- `src/langbot/pkg/api/mcp/server.py`
- 对应的 `skills/` 文档
- 参数 schema 和安全说明

## 9. 监控与可观测性

控制思考量后，管理员需要判断质量、延迟和成本是否值得。建议第二阶段增加：

- `reasoning_tokens`：从 `completion_tokens_details.reasoning_tokens` 或 Provider 等价字段提取。
- `effective_reasoning_level`：记录规范化后的生效档位，不记录原始思考内容。
- 模型监控页展示输入 token、可见输出 token、reasoning token、总延迟。
- Provider 不返回细分 token 时显示未知，不推算。

安全要求：日志、监控、debug API 默认都不得记录 reasoning 原文。思考内容可能包含敏感信息或系统提示，不应因为新增配置而扩大持久化范围。

## 10. 兼容与迁移

### 10.1 数据迁移

- 所有现有 LLM 记录迁移为 `{"level":"provider_default"}`。
- 不自动解析或迁移现有 `extra_args` 中的 reasoning 参数，避免误判嵌套结构和 Provider 语义。
- UI 检测到旧 `extra_args` reasoning 字段时显示“由高级参数控制”，统一策略保持 Provider Default。
- 用户主动改成统一策略时，要求先移除冲突高级参数。

### 10.2 运行时兼容

- `provider_default` 不产生任何新增请求参数。
- 不改变现有 `remove-think` 的存储键和默认值。
- 不改变已有 Provider 的 `litellm_provider`，除非该 Provider 在专项回归后单独切换。
- `drop_params` 不能用于掩盖显式 reasoning 配置错误；显式策略被丢弃应视为失败。
- 自托管和 toB 环境中的自定义兼容接口保持可用，未知能力不阻止 Provider Default 请求。

## 11. 实施拆分

### Phase 1：统一基础设施与主流 Provider

- Alembic 增加 `llm_models.reasoning_config`。
- Backend 模型实体、CRUD、测试接口支持统一配置。
- LiteLLMRequester 增加能力查询、严格校验和参数翻译。
- 支持 OpenAI、Anthropic、Gemini、DeepSeek、xAI、Ollama、OpenRouter 的已验证 LiteLLM 路径。
- 修复结构化 reasoning 的非流式/流式保留。
- 模型面板增加 reasoning ability 与只读能力标识。
- Local Agent 主模型和每个 fallback 增加独立的请求级策略。

### Phase 2：国内 Provider

- 专项核对并支持 Volcengine/Doubao、Bailian/Qwen。
- 对相关 requester 的 `litellm_provider` 变更做独立回归，避免把 reasoning 功能和通用请求行为回归混在一起。
- 补齐扫描结果中的 reasoning capability。

### Phase 3：监控与评估

- 持久化 reasoning token 和生效策略。
- 监控页增加 reasoning 成本/延迟指标。
- 建立不同 effort 的离线质量、首 token 延迟、总耗时和 token 对比基线。

## 12. 测试方案

### 12.1 单元测试

- `ReasoningConfig` 所有合法/非法组合。
- `provider_default` 不产生任何新增参数。
- 显式配置覆盖模型/调用 `extra_args` 的顺序。
- reasoning 配置与高级参数冲突时拒绝。
- OpenAI 档位原样映射。
- Anthropic 档位映射，以及高级参数预算兼容。
- Gemini 2 budget、Gemini 3 level，以及不支持真正关闭时拒绝。
- DeepSeek 只显示/接受 toggle，非 `none` effort 不伪装成不同档位。
- Ollama 布尔与分级模型差异。
- Volcengine enabled/disabled/auto 翻译。
- 未知 Provider 只允许 Provider Default，或在显式测试后使用标准参数。
- 非流式 `reasoning_content` 保存到 `provider_specific_fields`。
- 流式 reasoning 分片累计后仍能 round-trip。
- Gemini thought signature 和工具调用现有测试不能回归。

### 12.2 服务与持久化测试

- 新建、读取、更新模型的 `reasoning_config`。
- Alembic 从当前 head 升级后默认值正确。
- 模型测试接口与真实 Local Agent 使用同一翻译函数。
- 旧模型、旧 `extra_args` 和 `remove-think` 行为不变。

### 12.3 前端测试

- 能力不同的模型显示正确控件。
- 离散滑杆只能停在后端返回的可用档位。
- 当前档位文字、键盘操作和 ARIA value text 正确。
- 仅开关模型、不可关闭模型、完整档位模型分别显示正确刻度。
- fallback 能力不兼容时阻止保存并给出明确提示。
- 中英文文案完整，移动端 Popover 不溢出。

### 12.4 Provider 冒烟测试

至少选取以下真实或可控 mock：

- 一个支持 `none` 的 OpenAI reasoning 模型。
- 一个不支持 `none` 的 reasoning 模型。
- 一个 Anthropic adaptive thinking 模型。
- 一个 Gemini 2.x 与一个 Gemini 3.x 模型。
- 一个 DeepSeek hybrid thinking 模型，执行两轮含工具调用对话。
- 一个 Ollama 本地 reasoning 模型。
- 一个 OpenAI-compatible 自定义网关，验证 Provider Default 完全不变。

每个模型比较 Provider Default、最低档、中档、高档或关闭，记录成功率、首 token 延迟、总耗时、总 token 和 reasoning token（若可用）。

## 13. 风险与控制

| 风险 | 影响 | 控制措施 |
| --- | --- | --- |
| 将“最低思考”误当成“关闭” | 用户以为节省了成本，实际仍在推理 | `can_disable` 严格校验，不静默降级 |
| 模型能力表过期 | 新模型无法配置或旧模型报错 | 能力未知时保守；允许测试；升级 LiteLLM 时回归 |
| 高 effort 导致延迟/费用陡增 | 用户体验和预算风险 | 默认 Provider Default；UI 提示；后续监控 reasoning token |
| `extra_args` 与统一配置冲突 | 实际生效值不可预测 | 保存/测试时拒绝冲突；统一策略最后应用 |
| reasoning 原文进入日志 | 敏感信息泄露 | 不记录原文，只记录策略和 token |
| 多轮 reasoning 丢失 | 工具调用或后续轮次失败/降质 | 结构化保存并 round-trip；流式专项测试 |
| 修改 Provider 路由造成通用回归 | 非 reasoning 请求也受影响 | 国内 Provider 路由放第二阶段，独立提交和回归 |

## 14. 需要审核确认的决策

1. **是否同意三层分离**：能力、策略、展示互不替代，保留 `remove-think` 仅控制展示。
2. **是否同意严格语义**：显式关闭无法准确执行时直接报错，不自动降为最低思考。
3. **是否同意请求级配置**：流水线按模型 UUID 保存挡位，不把产品配置塞进 `extra_args`。
4. **是否同意 Runner 边界**：仅 Local Agent 展示控制项，外部 Runner 由其外部系统管理模型策略。
5. **是否同意保守默认**：所有现有模型迁移为 Provider Default，不自动开启、关闭或迁移旧高级参数。
6. **是否把结构化 reasoning 保留纳入第一阶段**：这是 DeepSeek 多轮和工具调用正确性的必要条件，建议必须纳入。

## 15. 推荐审核结果

建议按以上 6 项全部通过，并将 Phase 1 作为一个完整功能单元实施。不要只增加前端开关或只在 `extra_args` 中写 `reasoning_effort`；那样虽然改动小，但会继续混淆展示与推理、无法处理 Provider 差异，也无法保证多轮对话正确性。

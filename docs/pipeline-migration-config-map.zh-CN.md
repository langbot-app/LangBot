# 旧流水线迁移：配置去向与语义变更

本文对应迁移规划器 v3。原生行为基线：`9b7ba0d64708496ace30a82866f6dbc185f089dc`。

## 迁移边界

- 迁移只由用户在 UI 选择流水线并确认后执行。打开页面、预览、刷新、安装插件都不触发自动迁移。
- 流水线 ID、名称、Bot 绑定以及非 AI 配置保持不变。插件凭证、应用 ID、端点和模型配置仍属于本流水线，不迁入共享插件全局设置。
- 活动 AI 配置规范化为 `ai.runner` 与 `ai.runner_config`，避免编辑器把迁移结果判为混合旧配置。所有原始 AI 段（包括未选中的 Runner 配置）与完整原始配置一起保存到同一事务的持久化备份；预览会列出被归档的字段。
- 备份不是公开下载，也不意味着已有一键恢复 UI。未知提交结果不显示为已回滚；激活待重试只在新预览、重新选择并确认后执行，且不重复转换配置。
- “配置迁移”不等于“运行状态无损迁移”。原有远端会话、历史、Box 文件、待处理表单令牌不自动导入；UI 必须在确认前说明新会话/状态重置。自定义 Box 共享作用域与未结束的交互不能被静默清除。

## 功能与默认值的取舍

- LocalAgent 保留日期提示、结构化提示词、模型回退、模型专属推理配置、工具/知识库/沙箱能力；保留现代上下文预算、检查点和摘要机制，不恢复旧的 `max-round` 截断算法。
- `max-round` 退役，不把“10 轮”伪装成“50 条消息”等价换算；新上下文参数使用下面列明的默认值。工具执行仍显式采用 `serial`，不偷偷改变有副作用工具的执行顺序。
- Dify 旧保存项 `timeout` 并非原生 Runner 实际读取的超时控制。迁移采用新插件 30 秒默认值，并提示用户；旧任意数值只保存在备份中。
- Dify/Coze/N8n 迁移显式选择 `user-id-source=legacy-session`，Tbox 选择 `legacy-bot`；新建插件配置仍默认 `sender`。旧身份来自 Host 的可信会话/事件/机器人上下文，缺失时失败，不猜测为发送者。
- Dify/N8n 的旧身份使用原 `query.session`，Coze 使用原 `query`；不能在群聊、不同会话策略或恢复交互时把这两者混同。
- Coze、Langflow 等现代持久化远端会话机制保留；旧远端会话 ID 不跨账户、端点、Workspace 或 Runner 导入。
- DashScope 引用字段别名、Langflow 输入输出字段别名、Coze 历史开关别名分别归一化；冲突值阻断，而非靠字段出现顺序决定。
- N8n 的 ignore 响应模式、认证和保留身份字段要维持明确语义。普通业务变量保留支持的 JSON 值，内部/权限/敏感变量不无条件转发。
- `remove-think` 保留原输出策略，并与支持该字段的 Runner 参数同步；仅用户实际修改才传播，不把表单挂载默认值视为修改。
- 空字符串、缺失和显式 null 区分处理。WeKnora 的 agent-id 不得在打开/保存其他字段时被默认值替换；未知字段/类型不能靠 truthiness 静默接受。
- 工具、KB、MCP 的授权由 Host 校验；表单未显示的授权字段仍必须保留，不能因保存而删除或扩大权限。

## 插件版本要求

以下是本次本地源码的目标版本；本表不代表插件已经发布。旧版本即使名称相同，也不能作为新迁移能力的证明。

- `local-agent` → `LocalAgent` **0.1.6**。
- `dify-service-api` → `DifyAgent` **0.1.7**。
- `coze-api` → `CozeAgent` **0.1.7**。
- `dashscope-app-api` → `DashScopeAgent` **0.1.7**。
- `n8n-service-api` → `N8nAgent` **0.1.7**。
- `langflow-api` → `LangflowAgent` **0.1.7**。
- `deerflow-api` → `DeerFlowAgent` **0.1.7**。
- `tbox-app-api` → `TboxAgent` **0.1.5**。
- `weknora-api` → `WeKnoraAgent` **0.1.7**。

## 逐字段完整清单

共 9 类 Runner、104 条字段条目；按消费者展开共享字段。未知部署自定义键不冒充已穷举字段，遇到时阻断并保留原值。

目标路径缩写 `R` 表示 `config.ai.runner_config[当前插件 Runner ID]`；`extensions_preferences` 是流水线的 Host 扩展策略，不是插件全局配置。

### LocalAgent（28 项）

- **`ai.local-agent.box-session-id-template`** → `R.box-session-id-template`。
  - 全局、每会话、每用户、每对话上下文、每消息及有效自定义模板均原样保留；缺失时沿用插件默认 `{launcher_type}_{launcher_id}`。插件清单的 `allow_custom: true` 允许非预制值。空值、错误括号、位置参数、格式转换和属性访问会提示修正；公开请求变量保留，但运行时必须有值。复用范围保留不等于迁移旧容器及文件，新运行器按同样规则申请新的沙箱。
  - 所有权：Runner 管理复用策略、申请、绑定及附件传输；Host 管理连接、工作区隔离和配额。沙箱开关沿用 LocalAgent 插件默认 `true`，仅在有沙箱工具授权且平台支持时使用。
- **`ai.local-agent.enable-all-tools`** → `R.enable-all-tools`。
  - 原样复制有效授权；mcp 字段缺失时取 extensions_preferences 对应值；显式 null/错误类型不回退扩大权限。
  - 所有权：`host_policy_in_pipeline_runner_config`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:34`。
- **`ai.local-agent.knowledge-base`** → `R.knowledge-bases`。
  - 有效非空 plural 列表优先；plural 缺失/有效空列表且 singular 非空且非__none__→[原UUID]；非法容器/null单独校验，不以truthiness宽容；其他为空→[]。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:280`。
- **`ai.local-agent.knowledge-bases`** → `R.knowledge-bases`。
  - 有效非空 plural 列表优先；plural 缺失/有效空列表且 singular 非空且非__none__→[原UUID]；非法容器/null单独校验，不以truthiness宽容；其他为空→[]。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:278`。
- **`ai.local-agent.max-round`** → `退役；不生成同名活动参数`。
  - 活动目标省略 max-round；保留回滚备份和弃用通知；不把10轮映射成50条。
  - 所有权：`obsolete_native_context_control`；原生依据：`src/langbot/pkg/pipeline/msgtrun/truncators/round.py:13`。
- **`ai.local-agent.mcp-resource-agent-read-enabled`** → `R.mcp-resource-agent-read-enabled`。
  - 原样复制有效授权；mcp 字段缺失时取 extensions_preferences 对应值；显式 null/错误类型不回退扩大权限。
  - 所有权：`host_policy_in_pipeline_runner_config`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:133`。
- **`ai.local-agent.mcp-resources`** → `R.mcp-resources`。
  - 原样复制有效授权；mcp 字段缺失时取 extensions_preferences 对应值；显式 null/错误类型不回退扩大权限。
  - 所有权：`host_policy_in_pipeline_runner_config`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:129`。
- **`ai.local-agent.model`** → `R.model`。
  - 旧字符串UUID→{primary:原UUID,fallbacks:[],reasoning:{}}；对象深拷贝 primary/fallbacks/reasoning；不替换失效UUID、不扩大授权。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/localagent.py:283`。
- **`ai.local-agent.model.fallbacks`** → `R.model.fallbacks`。
  - 保留有序UUID列表，缺失=[]；runtime 去重不是迁移重排。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:93`。
- **`ai.local-agent.model.primary`** → `R.model.primary`。
  - 逐字复制非空UUID；Host 所有权交集校验，缺失不得选无关模型。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:92`。
- **`ai.local-agent.model.reasoning`** → `R.model.reasoning`。
  - 复制 UUID→level 映射，缺失={}；缺项保留模型持久默认；显式 provider_default 覆盖持久级别。
  - 所有权：`pipeline_selector_with_host_provider_policy`；原生依据：`src/langbot/pkg/provider/runners/localagent.py:284`。
- **`ai.local-agent.prompt`** → `R.prompt`。
  - 保留有序消息、合法SDK结构化内容、空消息、name/provider metadata；缺失不拿UI短提示词覆盖seed长提示词；空Host提示列表有权威性。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:122`。
- **`ai.local-agent.prompt[0].content`** → `R.prompt[0].content`。
  - 保留所有prompt记录的content，这里[0]仅默认记录形状；不把seed较长content替换为UI短默认，合法空content保留。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/metadata/pipeline/ai.yaml:121`。
- **`ai.local-agent.prompt[0].role`** → `R.prompt[0].role`。
  - 保留所有prompt记录的role，这里[0]仅默认记录形状；不把seed较长content替换为UI短默认，合法空content保留。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/metadata/pipeline/ai.yaml:120`。
- **`ai.local-agent.rerank-model`** → `R.rerank-model`。
  - 复制UUID；空字符串或__none__代表禁用；Host验证 rerank 授权。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/localagent.py:442`。
- **`ai.local-agent.rerank-top-k`** → `R.rerank-top-k`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/localagent.py:456`。
- **`ai.local-agent.tools`** → `R.tools`。
  - 原样复制有效授权；mcp 字段缺失时取 extensions_preferences 对应值；显式 null/错误类型不回退扩大权限。
  - 所有权：`host_policy_in_pipeline_runner_config`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:37`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。
- **`extensions_preferences.enable_all_mcp_servers`** → `extensions_preferences.enable_all_mcp_servers`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:127`。
- **`extensions_preferences.enable_all_plugins`** → `extensions_preferences.enable_all_plugins`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:126`。
- **`extensions_preferences.enable_all_skills`** → `extensions_preferences.enable_all_skills`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:339`。
- **`extensions_preferences.mcp_resource_agent_read_enabled`** → `extensions_preferences.mcp_resource_agent_read_enabled`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:135`。
- **`extensions_preferences.mcp_resources`** → `extensions_preferences.mcp_resources`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:131`。
- **`extensions_preferences.mcp_servers`** → `extensions_preferences.mcp_servers`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:149`。
- **`extensions_preferences.plugins`** → `extensions_preferences.plugins`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/pipelinemgr.py:142`。
- **`extensions_preferences.skills`** → `extensions_preferences.skills`。
  - 按原存在性和值保留；显式 false/空名单=不授权；无字段的旧有效缺省只有在同一所有权范围内可保留。
  - 所有权：`host_resource_authorization_shared_all_nine`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:344`。
- **`output.misc.remove-think`** → `R.remove-think`。
  - 复制严格 bool 到所选 Runner remove-think；同时保留 config.output.misc.remove-think；缺失=false。
  - 所有权：`pipeline_runner_parameters_plus_retained_host_output`；原生依据：`src/langbot/pkg/provider/runners/localagent.py:539`。

### DifyAgent（8 项）

- **`ai.dify-service-api.api-key`** → `R.api-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/difysvapi.py:838`。
- **`ai.dify-service-api.app-type`** → `R.app-type`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/difysvapi.py:833`。
- **`ai.dify-service-api.base-prompt`** → `R.base-prompt`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/difysvapi.py:984`。
- **`ai.dify-service-api.base-url`** → `R.base-url`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/difysvapi.py:842`。
- **`ai.dify-service-api.timeout`** → `R.timeout`。
  - 旧seed timeout=30没有被native Runner读取；native请求显式120。采用新插件30秒默认，旧任意保存值只留备份，不悄悄激活；用户可显式配置新timeout。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/default-pipeline-config.json:65`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。
- **`output.misc.remove-think`** → `R.remove-think`。
  - 复制严格 bool 到所选 Runner remove-think；同时保留 config.output.misc.remove-think；缺失=false。
  - 所有权：`pipeline_runner_parameters_plus_retained_host_output`；原生依据：`src/langbot/pkg/provider/runners/difysvapi.py:859`。

### CozeAgent（9 项）

- **`ai.coze-api.api-base`** → `R.api-base`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/cozeapi.py:35`。
- **`ai.coze-api.api-key`** → `R.api-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/cozeapi.py:31`。
- **`ai.coze-api.auto-save-history`** → `R.auto-save-history`。
  - 有效 underscore bool 为旧runtime值；仅hyphen有效bool时明确修复UI旧bug并取该值；两者有效且冲突需用户选择；缺失/null旧值明确弃用后采用目标 true；非bool(含空白字符串)拒绝，不bool()。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/metadata/pipeline/ai.yaml:566`。
- **`ai.coze-api.auto_save_history`** → `R.auto-save-history`。
  - 有效 underscore bool 为旧runtime值；仅hyphen有效bool时明确修复UI旧bug并取该值；两者有效且冲突需用户选择；缺失/null旧值明确弃用后采用目标 true；非bool(含空白字符串)拒绝，不bool()。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/cozeapi.py:34`。
- **`ai.coze-api.bot-id`** → `R.bot-id`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/cozeapi.py:32`。
- **`ai.coze-api.timeout`** → `R.timeout`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/cozeapi.py:33`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。
- **`output.misc.remove-think`** → `R.remove-think`。
  - 复制严格 bool 到所选 Runner remove-think；同时保留 config.output.misc.remove-think；缺失=false。
  - 所有权：`pipeline_runner_parameters_plus_retained_host_output`；原生依据：`src/langbot/pkg/provider/runners/cozeapi.py:50`。

### DashScopeAgent（8 项）

- **`ai.dashscope-app-api.api-key`** → `R.api-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/dashscopeapi.py:58`。
- **`ai.dashscope-app-api.app-id`** → `R.app-id`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/dashscopeapi.py:57`。
- **`ai.dashscope-app-api.app-type`** → `R.app-type`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/dashscopeapi.py:51`。
- **`ai.dashscope-app-api.references-quote`** → `R.references_quote`。
  - 有效 underscore 字符串优先；只有 hyphen 字符串则明确重命名修复；两者冲突需选择；都缺失采用“参考资料来自:”；显式空串和空白原样保留，null非字符串拒绝或用户明确选择默认。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/default-pipeline-config.json:71`。
- **`ai.dashscope-app-api.references_quote`** → `R.references_quote`。
  - 有效 underscore 字符串优先；只有 hyphen 字符串则明确重命名修复；两者冲突需选择；都缺失采用“参考资料来自:”；显式空串和空白原样保留，null非字符串拒绝或用户明确选择默认。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/dashscopeapi.py:59`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。
- **`output.misc.remove-think`** → `R.remove-think`。
  - 复制严格 bool 到所选 Runner remove-think；同时保留 config.output.misc.remove-think；缺失=false。
  - 所有权：`pipeline_runner_parameters_plus_retained_host_output`；原生依据：`src/langbot/pkg/provider/runners/dashscopeapi.py:121`。

### N8nAgent（13 项）

- **`ai.n8n-service-api.auth-type`** → `R.auth-type`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:47`。
- **`ai.n8n-service-api.basic-password`** → `R.basic-password`。
  - 凭证字节原样复制；选用basic时同时显式 basic-encoding="latin1"（native aiohttp默认），插件新建默认utf-8不改；不支持编码字符应报安全错误而非改写。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:52`。
- **`ai.n8n-service-api.basic-username`** → `R.basic-username`。
  - 凭证字节原样复制；选用basic时同时显式 basic-encoding="latin1"（native aiohttp默认），插件新建默认utf-8不改；不支持编码字符应报安全错误而非改写。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:51`。
- **`ai.n8n-service-api.header-name`** → `R.header-name`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:57`。
- **`ai.n8n-service-api.header-value`** → `R.header-value`。
  - 原样复制包括空字符串；active header必须有合法header-name，不省略合法空value；隐藏/inactive字段仍保留。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:58`。
- **`ai.n8n-service-api.jwt-algorithm`** → `R.jwt-algorithm`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:55`。
- **`ai.n8n-service-api.jwt-secret`** → `R.jwt-secret`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:54`。
- **`ai.n8n-service-api.output-key`** → `R.output-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:41`。
- **`ai.n8n-service-api.response-handling`** → `R.response-handling`。
  - reply/ignore逐字复制；缺失reply；ignore现已实现2xx只读header、不读body、不输出；非2xx仍失败；不得留旧缺特性blocker。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:42`。
- **`ai.n8n-service-api.timeout`** → `R.timeout`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:38`。
- **`ai.n8n-service-api.webhook-url`** → `R.webhook-url`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/n8nsvapi.py:35`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。

### LangflowAgent（10 项）

- **`ai.langflow-api.api-key`** → `R.api-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/langflowapi.py:119`。
- **`ai.langflow-api.base-url`** → `R.base-url`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/langflowapi.py:118`。
- **`ai.langflow-api.flow-id`** → `R.flow-id`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/langflowapi.py:120`。
- **`ai.langflow-api.input-type`** → `R.input-type`。
  - underscore存在且合法字符串→对应hyphen；underscore缺失且hyphen缺失/chat→chat；仅hyphen非默认属于旧UI被忽略的意图，用户选修复为该值或维持chat；两者冲突需选择；underscore显式null/空白不能被or chat吞掉。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/metadata/pipeline/ai.yaml:692`。
- **`ai.langflow-api.input_type`** → `R.input-type`。
  - underscore存在且合法字符串→对应hyphen；underscore缺失且hyphen缺失/chat→chat；仅hyphen非默认属于旧UI被忽略的意图，用户选修复为该值或维持chat；两者冲突需选择；underscore显式null/空白不能被or chat吞掉。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/langflowapi.py:81`。
- **`ai.langflow-api.output-type`** → `R.output-type`。
  - underscore存在且合法字符串→对应hyphen；underscore缺失且hyphen缺失/chat→chat；仅hyphen非默认属于旧UI被忽略的意图，用户选修复为该值或维持chat；两者冲突需选择；underscore显式null/空白不能被or chat吞掉。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/templates/metadata/pipeline/ai.yaml:702`。
- **`ai.langflow-api.output_type`** → `R.output-type`。
  - underscore存在且合法字符串→对应hyphen；underscore缺失且hyphen缺失/chat→chat；仅hyphen非默认属于旧UI被忽略的意图，用户选修复为该值或维持chat；两者冲突需选择；underscore显式null/空白不能被or chat吞掉。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/langflowapi.py:82`。
- **`ai.langflow-api.tweaks`** → `R.tweaks`。
  - 目标接受dict或严格JSON object（递归保留null/false/0）；缺失/null/空串/JSON null→{}；空白串按新便利默认{}并记录；false/0/list拒绝；JSON重复键/NaN/Infinity/过深结构拒绝；坏JSON绝不降级{}。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/langflowapi.py:93`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。

### DeerFlowAgent（13 项）

- **`ai.deerflow-api.api-base`** → `R.api-base`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:61`。
- **`ai.deerflow-api.api-key`** → `R.api-key`。
  - 逐字保留字符串包括空白/空串；null或非string拒绝；仅缺失采用target_default。auth-header是完整Authorization值，非空优先于api-key。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:68`。
- **`ai.deerflow-api.assistant-id`** → `R.assistant-id`。
  - 逐字保留字符串包括空白/空串；null或非string拒绝；仅缺失采用target_default。auth-header是完整Authorization值，非空优先于api-key。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:70`。
- **`ai.deerflow-api.auth-header`** → `R.auth-header`。
  - 逐字保留字符串包括空白/空串；null或非string拒绝；仅缺失采用target_default。auth-header是完整Authorization值，非空优先于api-key。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:69`。
- **`ai.deerflow-api.max-concurrent-subagents`** → `R.max-concurrent-subagents`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:75`。
- **`ai.deerflow-api.model-name`** → `R.model-name`。
  - 逐字保留字符串包括空白/空串；null或非string拒绝；仅缺失采用target_default。auth-header是完整Authorization值，非空优先于api-key。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:71`。
- **`ai.deerflow-api.plan-mode`** → `R.plan-mode`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:73`。
- **`ai.deerflow-api.recursion-limit`** → `R.recursion-limit`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:77`。
- **`ai.deerflow-api.subagent-enabled`** → `R.subagent-enabled`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:74`。
- **`ai.deerflow-api.thinking-enabled`** → `R.thinking-enabled`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:72`。
- **`ai.deerflow-api.timeout`** → `R.timeout`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/deerflowapi.py:76`。
- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。

### TboxAgent（5 项）

- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。
- **`ai.tbox-app-api.api-key`** → `R.api-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/tboxapi.py:59`。
- **`ai.tbox-app-api.app-id`** → `R.app-id`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/tboxapi.py:58`。
- **`output.misc.remove-think`** → `R.remove-think`。
  - 复制严格 bool 到所选 Runner remove-think；同时保留 config.output.misc.remove-think；缺失=false。
  - 所有权：`pipeline_runner_parameters_plus_retained_host_output`；原生依据：`src/langbot/pkg/provider/runners/tboxapi.py:114`。

### WeKnoraAgent（10 项）

- **`ai.runner.expire-time`** → `config.ai.runner.expire-time`。
  - 原样保留非负整数；缺失=0，禁止用 token budget 替换。
  - 所有权：`pipeline_host_lifecycle`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:131`。
- **`ai.runner.runner`** → `config.ai.runner.id`。
  - 所有权：`pipeline_selector`；原生依据：`src/langbot/pkg/pipeline/preproc/preproc.py:73`。
- **`ai.weknora-api.agent-id`** → `R.agent-id`。
  - 原键缺失：明确写入按旧app-type的默认（chat quick-answer，agent smart-reasoning）；显式null/空串保持(线端省略agent_id)；其余字符串含空白逐字保留，不能因chat而覆盖历史smart ID。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:89`。
- **`ai.weknora-api.api-key`** → `R.api-key`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:38`。
- **`ai.weknora-api.app-type`** → `R.app-type`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:336`。
- **`ai.weknora-api.base-prompt`** → `R.base-prompt`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:65`。
- **`ai.weknora-api.base-url`** → `R.base-url`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:45`。
- **`ai.weknora-api.knowledge-base-ids`** → `R.knowledge-base-ids`。
  - 保留远端ID顺序/重复/字节；缺失或null→[]；无效元素/空白ID拒绝，不静默丢弃。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:90`。
- **`ai.weknora-api.timeout`** → `R.timeout`。
  - 源键存在时深拷贝原值；缺失时按下面 native_defaults 的实际读取语义或显式新默认处理。不得把 null/空字符串统一当作缺失。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:92`。
- **`ai.weknora-api.web-search-enabled`** → `R.web-search-enabled`。
  - 复制严格bool，缺失false；仅agent线端使用，chat保存true仍不激活。
  - 所有权：`pipeline_runner_parameters`；原生依据：`src/langbot/pkg/provider/runners/weknoraapi.py:91`。

## 新增参数与明确采用的默认值

这些值是新机制的默认值，不声称与旧行为一一等价。已存在且受支持的有效值按映射规则保留；必填凭证/端点不能由模板伪造。

### LocalAgent

```json
{
  "advanced-settings": false,
  "date-grounding": true,
  "timeout": 300,
  "retrieval-top-k": 5,
  "rerank-model": "",
  "rerank-top-k": 5,
  "max-tool-iterations": 100,
  "tool-execution-mode": "serial",
  "max-tool-result-chars": 20000,
  "context-history-fetch-limit": 50,
  "context-window-tokens": 200000,
  "context-reserve-tokens": 16384,
  "context-keep-recent-tokens": 20000,
  "context-summary-tokens": 8000,
  "enable-all-tools": true,
  "tools": [],
  "knowledge-bases": []
}
```

### DifyAgent

```json
{
  "timeout": 30,
  "advanced-settings": false
}
```

### CozeAgent

```json
{
  "auto-save-history": true,
  "advanced-settings": false
}
```

### DashScopeAgent

```json
{
  "references_quote": "参考资料来自:",
  "timeout": 120,
  "advanced-settings": false
}
```

### N8nAgent

```json
{
  "auth-type": "none",
  "basic-username": "",
  "basic-password": "",
  "jwt-secret": "",
  "jwt-algorithm": "HS256",
  "header-name": "",
  "header-value": "",
  "timeout": 120,
  "output-key": "response",
  "response-handling": "reply",
  "basic-encoding": "latin1",
  "advanced-settings": false
}
```

### LangflowAgent

```json
{
  "input-type": "chat",
  "output-type": "chat",
  "tweaks": {},
  "advanced-settings": false
}
```

### DeerFlowAgent

```json
{
  "api-key": "",
  "auth-header": "",
  "assistant-id": "lead_agent",
  "model-name": "",
  "thinking-enabled": false,
  "plan-mode": false,
  "subagent-enabled": false,
  "max-concurrent-subagents": 3,
  "timeout": 300,
  "recursion-limit": 1000
}
```

### TboxAgent

```json
{
  "timeout": 120
}
```

### WeKnoraAgent

```json
{
  "knowledge-base-ids": [],
  "web-search-enabled": false,
  "timeout": 120,
  "base-prompt": "请回答用户的问题。",
  "advanced-settings": false
}
```

## 验证与交付状态

本清单负责说明所有已识别旧字段的去向和语义；不替代最终的集成验收。源码修改、插件打包、OSS/Cloud 持久化与权限、真实 SDK 调用、浏览器测试、独立审查和发布状态必须分别记录，不能以其中一项通过宣称全部完成。

源码库存与每条字段的多处原生证据、默认值/表达式及哈希见工作区的 `411-completion-config-audit.json` 和其标注的原始库存；最终验证以 `411-completion-*` 的实际日志和源码哈希为准。

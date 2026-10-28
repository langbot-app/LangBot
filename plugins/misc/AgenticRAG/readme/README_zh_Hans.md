# AgenticRAG

AgenticRAG 将当前 pipeline 已配置的知识库暴露为一个可供 Agent 调用的工具，使 Agent 可以先查看可用知识库，再按需检索相关内容。

## 作用

- 提供一个工具：`query_knowledge`
- 支持两个动作：
  - `list`：列出当前 pipeline 可见的知识库
  - `query`：从一个或多个指定知识库中检索相关文档片段
- 以 JSON 形式返回结果，便于 Agent 继续分析、总结和回答

## 整体设计

AgenticRAG 并不是一个新的 RAG 引擎，而是一个“控制检索时机”的插件。

它改变的重点不是底层怎么搜，而是**谁来决定什么时候搜**：

- 不再由 runner 在回答前固定做一次自动检索
- 改为让模型先判断当前问题是否需要查知识库
- 模型可以先看有哪些 KB，再选择一个或多个 KB 检索
- 只有模型显式调用工具时，检索才真正发生

这样设计是为了解决 naive RAG 的典型问题：虽然简单，但它会在很多并不需要检索的轮次里提前注入噪声、浪费上下文，还可能把不相关片段带进推理过程。

## 实现机制

本插件本身并不实现新的 RAG 引擎，而是对 LangBot 已有的按 `query_id` 作用域隔离的知识库能力做了一层工具封装：

- `list_pipeline_knowledge_bases()`：列出当前 query 所属 pipeline 可访问的知识库
- `retrieve_knowledge()`：对一个或多个指定知识库执行检索，返回合并后的 top-k 条结果

工具被调用时，运行时会自动注入当前会话对应的 `query_id`。插件内部通过 `QueryBasedAPIProxy` 持有这个上下文，因此业务侧只需要传：

- `kb_id` 或 `kb_ids`
- `query_text`
- `top_k`

虽然底层运行时支持 metadata filters，但本插件目前没有在 Agent 流的工具调用中把原始元数据过滤能力直接暴露给大模型。原因是不同知识引擎和向量后端对 metadata 字段、字段类型、值格式和过滤语义的约定并不统一，而当前 Agent 侧也没有稳定的 schema 来源来正确构造这些过滤条件。

后续如果生态里能够为每个知识库提供更统一的可过滤字段与操作符描述方式，我们可以再考虑把 metadata filter 能力开放给 Agent 使用。

## 它是怎么工作的

一次 AgenticRAG 请求，大致分成四步：

### 1. 关闭 naive RAG

在 `PromptPreProcessing` 阶段，插件会先判断当前使用的 LLM 是否支持 tool call：

- 如果支持 tool call，就清空 runner 当前的 `_knowledge_base_uuids`，关闭默认 naive RAG 前置检索
- 如果不支持 tool call，就保留 naive RAG，避免知识库检索链路被完全切断

### 2. 注入检索策略 system prompt

与此同时，AgenticRAG 还会额外注入一条 system prompt，明确告诉模型：

- 当前配置的知识库是领域信息的主要真相来源
- 不存在自动检索兜底
- 面对事实、规则、流程、产品、配置等领域问题时，应优先调用 `query_knowledge`

这是因为只靠 tool description 往往不足以稳定改变模型行为，所以当前实现采用了更强的 system prompt + tool prompt 双层约束。

### 3. 让模型先看 KB，再主动查询

之后模型可以按两步走：

- `action="list"`：先查看当前有哪些 KB 可用
- `action="query"`：再决定查一个 KB，还是并行查多个 KB

其中：

- 单库检索优先用 `kb_id`
- 多库并行检索时才用 `kb_ids`

### 4. 以结构化 JSON 返回结果

工具会合并检索结果，补充 `knowledge_base_id` 等信息，并以 JSON 返回，便于模型继续推理、继续调用工具，或者直接回答。

## 检索行为变化

启用 AgenticRAG 后，插件会禁用当前 pipeline 在 runner 里的 naive RAG 前置检索。

- 模型回答前不再自动注入知识库内容
- 是否检索知识库，改为由模型通过 `query_knowledge` 主动决定
- 如果模型不调用这个工具，本轮上下文里就不会出现任何知识库内容

但这里有一个重要例外：

- 如果当前 LLM 不支持 tool call，AgenticRAG 会保留 naive RAG，而不是强行关闭

这样可以减少“每次都全量先查一次”带来的噪声，但也意味着 prompt 设计会直接影响检索意愿。因此当前实现同时使用：

- `query_knowledge` 的 tool prompt
- `PromptPreProcessing` 注入的 system prompt

二者共同推动模型在事实、规则、流程、产品信息和其他领域知识问题上优先检索，而不是凭参数记忆作答。

## 为什么这么做

这个插件的设计目标很明确：

- 复用 LangBot 现有的知识库与检索基础设施
- 去掉不必要的“每轮都查一次”
- 把检索决策放回 agent loop
- 同时仍然保证访问范围严格受当前 pipeline 限制

与 naive RAG 相比，这样的取舍带来的好处是：

- 不需要知识库的轮次里，上下文更干净
- 模型可以显式决定查哪个 KB
- 可以支持“先 list、再 query、必要时再 query 一次”的多步检索

代价也很明确：

- 如果模型完全不调用工具，那本轮就拿不到任何 KB 内容

所以 AgenticRAG 不能只靠“让模型自己悟到要检索”，而必须额外通过 system prompt 和 tool prompt 明确塑造检索偏好。

这也是为什么当前实现增加了“先判断 tool call 能力再决定是否关闭 naive RAG”的保护逻辑。否则，一旦把 AgenticRAG 用在不支持 tool call 的模型上，知识库检索会直接失效。

## 安全设计

本插件只允许访问当前 pipeline 配置过的知识库。

- LangBot 运行时也会再次校验 `kb_id` 是否属于当前 pipeline

因此，即使模型因为 prompt 注入尝试构造其他知识库 ID，也不应越权访问未授权的知识库。

## 使用方法

1. 安装并启用本插件。
2. 在当前 pipeline 的 local agent 配置中绑定一个或多个知识库。
3. 让 Agent 调用 `query_knowledge`：
   - 先使用 `action="list"` 查看可用知识库
   - 再使用 `action="query"`，单库检索时传入 `kb_id`，多库并行检索时传入 `kb_ids`
   - 同时传入 `query_text`，以及可选的 `top_k`（作用于合并后的结果集）

## 参数说明

当 `action="query"` 时，可用参数如下：

- `kb_id`：单库检索时的目标知识库 UUID
- `kb_ids`：多库并行检索时的目标知识库 UUID 数组；只有并行查多个 KB 时才使用
- `query_text`：检索查询文本
- `top_k`：可选，返回结果数量，必须为正整数，默认值为 `5`，作用于合并后的结果集

如果多库并行检索时部分知识库失败、部分成功，工具会返回一个包含 `results` 和 `failed_kbs` 的 JSON 对象，便于 Agent 继续使用部分成功结果。

## 典型调用流程

1. Agent 先列出当前可用知识库。
2. 根据知识库名称和描述选择一个或少量合适的 KB。
3. 使用明确、具体的查询语句执行检索。
4. 基于返回的片段内容继续回答问题或执行下一步推理。

## Prompt 设计意图

当前 prompt 层重点向模型传达两件事：

- 知识库是当前对话里领域信息的权威来源
- 启用 AgenticRAG 后，不再存在自动检索兜底

如果不显式强调这两点，LLM 很容易高估自己的预训练知识，降低检索频率。因此当前实现不是只靠 tool prompt，而是把同样的检索策略同时放进 system prompt 和 tool prompt 两层。

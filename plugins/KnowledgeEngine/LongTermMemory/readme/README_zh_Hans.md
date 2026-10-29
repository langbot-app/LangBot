# LongTermMemory

LangBot 长期记忆插件，采用双层记忆设计：

- L1 核心画像：注入到 system prompt
- L2 情景记忆：通过向量检索召回后注入

## 作用

- 提供 `remember` 工具，用于写入情景记忆
- 提供 `recall_memory` 工具，用于主动检索情景记忆并使用受控过滤条件
- 提供 `update_profile` 工具，用于更新稳定画像信息
- 提供 `forget` 工具，用于让 Agent 删除指定 ID 的情景记忆
- 通过 EventListener 自动注入画像和当前说话人身份
- 通过 EventListener 在模型调用前自动检索并注入相关情景记忆
- 提供 `!memory` 命令用于查看和调试记忆状态
- 提供网页版**记忆控制台**，用于可视化查看：画像、情景记忆（支持分页）、审计日志、导出、metadata 隔离健康检查，以及最近一次记忆注入快照
- 提供 `!memory list [page]` 命令，用于分页浏览情景记忆
- 提供 `!memory forget <episode_id>` 命令，用于删除单条情景记忆
- 提供 `!memory search <query>` 命令，用于搜索情景记忆（结果包含 episode ID）
- 提供 `!memory export` 命令，将当前会话范围内的 L1 画像导出为 JSON
- 当存入带有 `correction` / `fact-update` / `clarification` 标签的新记忆时，会自动将相关旧记忆标记为 superseded

## 整体设计

这个插件的目标不是做一个“把所有历史对话都塞进上下文”的记忆系统，而是把长期记忆拆成两层，分别处理“稳定事实”和“具体经历”：

- **L1 核心画像**：低频变化、相对稳定的信息，例如名字、偏好、身份、长期备注。
- **L2 情景记忆**：带时间性和情境性的内容，例如最近做过什么、提过什么计划、发生过什么事件。

这样拆分的原因是：

- 稳定画像适合直接注入 system prompt，成本低、命中稳定。
- 情景记忆数量会不断增长，不适合每轮都全量注入，更适合按 query 做检索召回。
- Agent 对“稳定画像”和“事件记忆”的写入方式也不同，前者更适合结构化更新，后者更适合追加式记录。

## 与 OpenClaw 这类个人助手记忆方案的区别

最近不少 Agent 系统会讨论类似 OpenClaw 这样的记忆实现：把长期记忆主要做成用户可直接阅读和编辑的文本文件，例如 `MEMORY.md`，再配合摘要、反思和少量检索逻辑来完成“个人助手式”的长期记忆。

这种方案有它明确的优点：

- 记忆对用户完全透明，可直接检查和修改
- 纯文本天然适合备份、同步、版本控制
- 对单用户、单助手、强连续性的个人场景非常自然
- 当记忆规模不大时，全文理解确实可能“足够好”

但 LangBot 的长期记忆插件面对的不是完全相同的问题。我们更常见的运行场景是：

- 一个 bot 同时服务多个群聊和私聊
- 同一个插件实例要处理多个会话、多个说话人
- 记忆不仅是“我和助手”的私人连续叙事，还包括群共享背景、当前说话人的稳定画像、以及会话级事件记忆
- 系统要明确控制不同会话、不同 bot、不同说话人之间的隔离边界

因此，我们没有直接采用“单一文本记忆文件作为长期记忆真相源”的方案，而是选择了更适合 LangBot 场景的分层设计。

### OpenClaw 方案更像什么

如果把它抽象一下，OpenClaw 更像是：

- **面向单用户个人助手**
- **以可读文本为长期记忆主形态**
- **强调透明、可编辑、叙事连续性**
- **默认假设记忆规模可控，且用户愿意直接参与维护**

这非常适合“个人 AI 助手 / 日志伙伴 / 研究搭子”一类产品。

### LangBot 插件为什么不直接这么做

LangBot 的长期记忆插件更关注的是“多会话、多说话人、可隔离、可检索、可控注入”的运行条件。

如果直接把长期记忆主形态做成类似 `MEMORY.md` 的单一文本文件，会很快遇到这些问题：

- **隔离困难**
  - 群 A、群 B、私聊 C 的记忆如何安全共存？
  - 某个说话人的稳定画像如何从共享叙事文本里精确拆出来？
- **注入粒度不稳定**
  - system prompt 里需要的是稳定画像，不是整个时间线叙事
  - 自动 recall 需要的是与当前 query 最相关的片段，而不是整本文本日记
- **多用户边界不清晰**
  - 在个人助手里，“用户”通常只有一个
  - 在 LangBot 里，“当前说话人”“当前会话”“当前 bot”是三个都需要认真处理的维度
- **主动检索与自动注入是两类不同需求**
  - 稳定画像适合固定注入
  - 情景记忆适合检索后注入
  - 如果都揉成同一种文本记忆形态，工程上会变得很别扭

### 我们当前设计的取舍

所以 LongTermMemory 的设计，本质上是在做下面这个取舍：

- **借鉴 OpenClaw 的地方**
  - 承认“长期记忆不该只是黑盒向量索引”
  - 重视可解释性、稳定画像、时间性记忆和长期行为调整
  - 接受“不是所有记忆都应该一股脑塞进上下文”

- **与 OpenClaw 不同的地方**
  - 我们没有把文本日记作为唯一记忆主形态
  - 我们把稳定画像和情景记忆显式拆层
  - 我们优先解决多会话、多说话人、多 bot 的隔离问题
  - 我们让 L2 记忆天然进入 LangBot 的 KB / 检索体系，而不是只靠全文理解

可以把两者理解成：

- OpenClaw 主要回答的是“个人助手如何拥有可读、可控、可反思的长期记忆”
- LongTermMemory 主要回答的是“群聊 / 私聊混合场景下，bot 如何在安全隔离前提下拥有稳定画像与可检索经验记忆”

这不是谁比谁“更先进”，而是产品目标不同导致的设计重心不同。

## 设计说明

本插件尽量复用 LangBot 现有的扩展点，而不是依赖额外的核心补丁：

- L1 画像存储在插件存储中，格式为 JSON
- L2 情景记忆存储在向量数据库中
- 通过将本插件的 KnowledgeEngine 绑定到 pipeline，实现按 pipeline 显式启用
- 当前实现假设每个插件实例只维护一个 memory KB，并通过 metadata 做隔离

当前实现是围绕现有 LangBot 和 SDK API 设计的。后续如果 LangBot 提供更明确的 memory API、session 身份 API 或 KB 注册 API，插件可以进一步简化，但现有架构本身不需要因此推翻。

### 向量数据库后端兼容性

L2 情景记忆依赖任意 metadata 字段（例如 `user_key`、`episode_id`、`tags`、`importance`）做隔离与过滤。不是所有 LangBot 向量数据库后端都支持任意 metadata：

| 后端 | 任意 metadata | LongTermMemory 支持情况 |
|------|---------------|-------------------------|
| **Chroma**（默认） | 是 | 完整支持 |
| **Qdrant** | 是 | 完整支持 |
| **SeekDB** | 是 | 完整支持 |
| **Milvus** | 否（固定 schema：`text`、`file_id`、`chunk_uuid`） | 不支持 |
| **pgvector** | 否（固定 schema：`text`、`file_id`、`chunk_uuid`） | 不支持 |

Milvus 和 pgvector 会静默丢弃它们不认识的 metadata 字段。这意味着基于 metadata 的隔离（如 `user_key`）以及 `!memory list`、`!memory forget`、`!memory search` 这类命令在这些后端上都不能正确工作，过滤条件可能被忽略，结果也可能失去作用域约束。

如果要使用 LongTermMemory，请优先选择 Chroma、Qdrant 或 SeekDB 作为向量数据库后端。

## 它是怎么工作的

一次完整的长期记忆流程，大致分成四部分：

### 1. L1 画像写入

- Agent 通过 `update_profile` 工具写入稳定信息。
- 数据写入插件存储（plugin storage），按 `session` 或 `speaker` 维度保存。
- 这些画像不是向量数据，不进入知识库，而是以结构化 JSON 存储。

### 2. L2 情景记忆写入

- Agent 通过 `remember` 工具写入事件型记忆。
- 记忆内容会带上时间、重要度、标签、scope 等 metadata。
- 这些内容进入 LongTermMemory 的 KnowledgeEngine，经过 embedding 后写入向量库。

### 3. 对话前自动注入

- 在 `PromptPreProcessing` 阶段，EventListener 会先解析当前会话身份。
- L1 部分：
  - 读取 session profile
  - 读取当前说话人的 speaker profile
  - 把当前说话人身份信息一起注入到 `default_prompt`
- L2 部分：
  - 使用当前用户消息做一次情景记忆检索
  - 命中的记忆以“事实数据”形式注入到 prompt

也就是说，L1 和 L2 都是在模型真正回答前进入上下文，但注入方式不同：L1 走 system prompt，L2 走检索结果块。

### 4. 主动检索与调试

- 如果自动注入不足，Agent 还可以通过 `recall_memory` 工具主动检索记忆。
- 开发或排障时，可以使用 `!memory`、`!memory profile`、`!memory search`、`!memory list`、`!memory forget` 查看当前状态。
- `!memory export` 只导出当前 scope 下的 L1 画像，方便做备份或迁移。

## 与 AgenticRAG 的关系

如果同时启用了 AgenticRAG：

- LongTermMemory 会先把自己的 memory KB 从 naive RAG 预处理列表里移除。
- L2 自动记忆召回仍由 LongTermMemory 自己完成。
- 同一个 memory KB 仍然可以被 AgenticRAG 的 `query_knowledge` 工具主动访问，用于更深一步的 agentic 检索。

这样设计的好处是：

- 自动记忆召回不会和 naive RAG 重复
- 长期记忆仍然保留“自动 recall + 主动 query”两条路径
- 不依赖插件加载顺序来避免重复注入

## 为什么暂时不向 Agent 开放元数据过滤

虽然底层运行时支持 metadata filter，但本插件目前没有在 Agent 流中直接暴露任意原始元数据过滤能力。

原因包括：

- 不同知识引擎和向量后端没有统一的 metadata schema
- 过滤字段名、值格式、支持的操作符可能各不相同
- Agent 当前没有稳定的 schema 来源，难以正确构造过滤条件

如果未来 LangBot 能为每个知识库提供统一的可过滤元数据字段描述，就可以再考虑开放更通用的 Agent 侧 metadata filter。

不过，由于长期记忆插件自己的 memory schema 是稳定的，本插件已经提供了受控的 `recall_memory` 工具入口，支持按说话人、时间范围等固定参数主动检索记忆，而不是让大模型直接拼接底层 raw filter。

## 隔离模型

支持两种隔离模式：

- `session`：每个群聊或私聊各自独立
- `bot`：同一个 bot 下的所有会话共享记忆

在当前部署模型下，这通常已经足够，因为插件实例一般会绑定在特定的 LangBot 运行环境或 bot 上。

## 隔离规则细节

这个插件里实际上有两套相关但不完全相同的“作用域”概念：

- **session_name**：当前 query / retrieval 链路里传递的会话标识，格式是 `{launcher_type}_{launcher_id}`。
- **session_key**：插件内部用于 L1 画像存储的 key；如果有 `bot_uuid`，实际会变成 `{bot_uuid}:{launcher_type}_{launcher_id}`，否则退化为 `{launcher_type}_{launcher_id}`。
- **scope_key / user_key**：真正用于画像存储或 L2 检索隔离的键。

### L1 画像怎么隔离

L1 画像总是按当前会话范围保存：

- `session profile`
  - 对应当前会话共享画像
  - 例如群聊共同背景、当前会话共享约定
- `speaker profile`
  - 对应当前说话人的稳定画像
  - 例如某个成员的偏好、身份、长期备注

因此，`!memory export` 导出的也是**当前 session_key 对应范围**下的画像，而不是整个插件实例里的全部画像。

### L2 情景记忆怎么隔离

L2 情景记忆在写入向量库时会带上隔离 metadata，检索时再按隔离规则过滤：

- `session`
  - 群 A 的记忆不会被群 B 召回
  - 私聊 A 的记忆不会被私聊 B 召回
- `bot`
  - 同一个 bot 下的多个会话共享一套 L2 记忆
  - 适合希望 bot 在不同会话之间共享长期经验的场景

如果还带有 `sender_id`，插件也可以优先检索“当前说话人相关”的记忆，再回退到更宽的 scope。

### 为什么 L1 和 L2 的隔离看起来不完全一样

这是有意为之：

- L1 更像“当前会话和当前说话人的稳定画像”，天然适合做精细的 session / speaker 级存储。
- L2 更像“可检索的经验库”，更适合通过 metadata 过滤控制召回范围。
- 这样既保留了 L1 的精确注入能力，也保留了 L2 的可扩展检索能力。

## 使用方法

1. 安装并启用本插件。
2. 使用本插件的 KnowledgeEngine 创建一个 memory knowledge base。
3. 配置以下参数：
   - `embedding_model_uuid`
   - `isolation`
   - 可选 `recency_half_life_days`
   - 可选 `auto_recall_top_k`
4. 让 Agent 使用：
   - `remember` 记录事件、计划、情景事实
   - `recall_memory` 在自动召回不足时主动检索记忆
   - `update_profile` 记录稳定偏好和画像信息
   - `forget` 按 ID 删除单条情景记忆
5. 使用 `!memory`、`!memory profile`、`!memory search <query>`、`!memory list [page]`、`!memory forget <id>`、`!memory export` 查看记忆状态。

## 给其他插件共享上下文

LongTermMemory 会在每次 `PromptPreProcessing` 事件期间，把结构化上下文摘要写入 query variable `_ltm_context`。其他插件可以读取这个变量，在完全不依赖 LongTermMemory 代码的前提下，基于用户记忆做程序化决策。

### 变量名

`_ltm_context`

### 数据结构

```python
{
    "speaker": {
        "id": "user_123",           # sender_id，可能为空字符串
        "name": "Alice",            # sender_name，可能为空字符串
    },
    "session_profile": {            # 总是存在，但字段可能为空
        "name": "",
        "traits": ["creative", "analytical"],
        "preferences": ["prefers detailed explanations"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "speaker_profile": {            # sender_id 不可用时为 null
        "name": "Alice",
        "traits": ["extroverted"],
        "preferences": ["likes humor"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "episodes": [                   # 自动召回的 L2 情景记忆，可能为空
        {"content": "User mentioned a trip to Beijing last week"},
    ],
}
```

### 使用示例

```python
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider.message import Message


class PersonalityCustomizer(EventListener):
    def __init__(self):
        super().__init__()

        @self.handler(events.PromptPreProcessing)
        async def on_prompt(event_ctx: context.EventContext):
            ltm = await event_ctx.get_query_var("_ltm_context")
            if not ltm:
                # LongTermMemory 未安装或未启用时，走默认行为
                return

            profile = ltm.get("speaker_profile") or ltm.get("session_profile") or {}
            traits = profile.get("traits", [])

            if "喜欢幽默" in traits:
                style = "Use a humorous and playful tone."
            elif "偏好简洁" in traits:
                style = "Be concise and direct."
            else:
                return

            event_ctx.event.default_prompt.append(
                Message(role="system", content=style)
            )
```

### 设计说明

- 如果 LongTermMemory 未安装，`_ltm_context` 不存在。消费方插件应把 `None` 视为正常情况，并回退到默认行为。
- 如果 LongTermMemory 已启用但还没有画像数据，变量会存在，但字段为空。这样消费方可以区分“没有记忆插件”和“记忆插件已启用但暂无数据”。
- 双方只依赖变量名和 schema 约定，不依赖对方代码。如果未来用另一个记忆插件替换 LongTermMemory，只要它写同样的 key 和 schema，消费方插件就无需改动。
- LongTermMemory 需要在事件分发顺序上先于消费方插件运行。实际效果通常取决于插件安装顺序。

## 导入与导出

- **导出（L1 画像）：** 使用 `!memory export` 命令导出当前 `scope_key` 下的 session 画像和 speaker 画像，格式为 JSON，可复制保存用于备份或迁移。该命令不会跨 session / scope 导出其他会话的数据。
- **导入（L2 情景记忆）：** 通过 LangBot 知识库前端界面上传 JSON 文件，批量导入情景记忆。
- **L2 情景记忆现在支持浏览**：可通过 `!memory list [page]` 分页查看，也可以通过 `!memory forget <id>` 删除单条情景记忆。完整批量导出仍未实现。

## 关键技术问答

### Q1. 为什么 L1 和 L2 要分层，而不是统一存在向量库里？

因为两类信息的访问模式完全不同：

- L1 是稳定事实，适合每轮都稳定注入
- L2 是事件型记忆，适合按 query 检索

如果把两者都放进向量库：

- 稳定画像会变得不稳定，容易漏召回
- 每轮都查会浪费上下文和检索预算
- 写入和更新语义也会变混乱

### Q2. L2 记忆为什么不全量注入，而要检索？

因为 L2 会不断增长。全量注入会带来几个直接问题：

- prompt 很快膨胀
- 噪声越来越大
- 旧记忆会挤占真正相关的上下文

所以当前策略是：

- 自动召回一小部分最相关记忆
- 不够时再让 Agent 通过 `recall_memory` 主动查

### Q3. L2 记忆有时间衰退吗？

有。

L2 检索不是只看向量相似度，还会结合时间衰退做重排。越新的记忆通常权重越高，越旧的记忆权重会逐步下降。

当前实现里使用的是“半衰期”思路：

- 一条记忆在达到 `half_life_days` 时，时间权重衰减到约 50%
- 越新的记忆越容易排在前面
- 但旧记忆不会被直接删除，只是排序优势变弱

这样做的目的不是“自动遗忘所有旧事”，而是让检索结果更符合“近期上下文优先”的使用直觉。

### Q4. 旧记忆会不会彻底失效？

不会自动彻底失效。

时间衰退影响的是排序，不是硬删除。只要内容仍然足够相关，旧记忆仍可能被召回。

真正删除通常发生在：

- 你显式删除文档 / 知识库内容
- 重建知识库
- 替换插件实例或数据

### Q5. `session` 和 `bot` 隔离模式怎么选？

经验上可以这样理解：

- 选 `session`
  - 适合把每个群 / 私聊都当成独立人格上下文
  - 更安全，串话风险更低
- 选 `bot`
  - 适合希望 bot 跨会话共享长期经验
  - 召回面更大，但也更容易把别的会话经验带进来

如果你不确定，默认优先 `session`。

### Q6. 为什么 `!memory export` 只导出当前 scope？

这是刻意的安全边界，不是功能没做完。

如果默认能导出整个插件实例下的所有 L1 画像，就很容易发生跨会话、跨用户的数据泄漏。当前实现只允许导出当前 `scope_key` 下的数据，更符合“最小暴露面”的原则。

### Q7. 如果运行时没有把 `_knowledge_base_uuids` 放进 query variables，会发生什么？

自动记忆注入本身仍然可以工作，但插件无法把自己的 memory KB 从 naive RAG 预处理中移除。

这会导致重复召回：

- 一份由 LongTermMemory 自己注入
- 另一份又被 runner 的通用知识库流程检索出来

所以这不是“完全失效”，而是会造成上下文冗余和噪声增加。

### Q8. 为什么 L2 还不支持导出？

SDK 现在已经提供了 `vector_list` API，可以分页枚举向量库内容。LongTermMemory 因此支持了通过 `!memory list [page]` 浏览 L2 情景记忆，以及通过 `!memory forget <episode_id>` 或 `forget` 工具逐条删除。

完整的批量导出还没有实现，但底层构件已经具备。

### Q9. 和 AgenticRAG 同时启用时会不会重复召回？

当前设计就是为了解决这个问题：

- LongTermMemory 会主动移除自己的 naive RAG 预处理
- L2 自动 recall 由 LongTermMemory 自己完成
- 如果模型还需要更深入查询，同一个 memory KB 还可以通过 AgenticRAG 主动查询

所以它们是互补关系，不是简单叠加两次同样的召回。

## 记忆控制台

除了 `!memory` 命令外，插件还提供一个网页版**记忆控制台**（注册为插件的 Page 组件），用于可视化查看与维护。它通过受作用域约束的页面接口与插件通信，所有操作都不会越过当前选中的记忆空间。

控制台由「记忆空间侧栏」和若干标签页组成：

- **记忆空间侧栏** —— 选择已有作用域，或填入 `bot_uuid` / `session_name` / `isolation` 并点击 **推导**，自动计算出对应的 `scope_key` 与 `user_key`；「高级 / 原始字段」区域向高级用户暴露底层 key。
- **画像** —— 查看当前作用域的会话画像和当前说话人画像。
- **情景记忆** —— 对当前 `user_key` 分页列出或语义搜索 L2 情景记忆，可按生命周期状态过滤，并就地归档、恢复或删除单条记忆。每个写操作都会写入作用域审计条目，与对应的 `!memory` 命令一致。
- **注入快照** —— 加载该作用域**最近一次记忆注入快照**：本轮是否注入、注入了多少 block 和字符、当前说话人、所用的会话/说话人画像，以及自动召回的 L2 情景记忆。无需翻日志即可回答「机器人上一轮到底记住了什么」。
- **审计** —— 分页浏览并导出作用域审计日志。
- **导出** —— 将当前作用域的 L1 画像和 L2 情景记忆导出为 JSON。
- **诊断** —— 点击 **运行健康检查**，可直接在界面中执行与 `!memory health` 相同的 metadata 隔离探针（知识库配置、embedding 模型，以及 search / list / delete 上的 `user_key` 过滤隔离），以红/黄/绿状态卡片呈现。在信任作用域召回之前建议先运行，尤其是上文列为「不支持」的后端。注意：控制台无法验证知识库是否已挂载到某条具体的流水线——这一项请在流水线中运行 `!memory health` 确认。

控制台支持 i18n（`en_US`、`zh_Hans`），并跟随宿主 LangBot 的明暗主题。

## 组件

- KnowledgeEngine: [memory_engine.py](../components/knowledge_engine/memory_engine.py)
- EventListener: [memory_injector.py](../components/event_listener/memory_injector.py)
- Tools: [remember.py](../components/tools/remember.py), [recall_memory.py](../components/tools/recall_memory.py), [update_profile.py](../components/tools/update_profile.py), [forget.py](../components/tools/forget.py)
- Command: [memory.py](../components/commands/memory.py)
- Page: [memory_console.py](../components/pages/memory_console/memory_console.py), [index.html](../components/pages/memory_console/index.html)

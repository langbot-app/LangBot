# LangRAG

LangRAG 是 LangBot 的 RAG（检索增强生成）知识引擎插件，用于基于 LangBot Host 内置的 Embedding 模型和向量数据库完成文档摄入、索引构建与知识库检索。

它适合作为 LangBot 的默认 RAG 引擎，也可以作为开发自定义 KnowledgeEngine 插件的参考实现。

## 功能特性

- **外部 Parser 集成**：优先使用 GeneralParsers 等 Parser 插件提供的预解析内容，包括结构化 `sections` 和文档 `metadata`
- **内置解析兜底**：未配置外部 Parser 时，可回退到插件内置解析器
- **多种索引策略**：支持平面分块、父子分块、LLM 生成问答对
- **灵活检索方式**：支持向量检索、全文检索和混合检索
- **查询改写**：支持 HyDE、Multi-Query、Step-Back，用于提升召回率
- **可配置分块**：支持自定义分块大小和重叠长度的递归字符切分
- **结构化分块**：当 Parser 返回结构化 sections 时，会尽量保留标题层级、页码信息和表格边界
- **上下文扩展**：可为每个命中 chunk 追加相邻 chunk，返回更完整的检索上下文
- **重排序**：支持使用 LangBot rerank 模型或 LLM 对候选结果重排
- **文档管理**：支持按文档删除已索引向量
- **可观测性页面**：提供摄入、检索、删除、Embedding 等操作的运行指标和诊断信息

## 架构

```text
┌─────────────────────────────────┐
│         LangBot Core            │
│  (Embedding / VDB / Storage)    │
└──────────┬──────────────────────┘
           │ RPC (IPC)
┌──────────▼──────────────────────┐
│          LangRAG                │
│  ┌───────────────────────────┐  │
│  │       Knowledge Engine    │  │
│  │  Parse → Chunk → Embed   │  │
│  │      → Store / Search    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

## 文档摄入流程

LangRAG 会优先使用 LangBot Host 提供的 Parser 输出：

1. LangBot 读取上传文件。
2. GeneralParsers 等 Parser 插件提取 `text`、`sections` 和 `metadata`。
3. LangRAG 直接消费结构化解析结果。
4. 如果没有 Parser 输出，LangRAG 回退到内置解析器。
5. 按所选索引策略构建 chunks 或 Q&A 对。
6. LangBot Host 生成 embedding，并将向量写入向量数据库。

因此，推荐将 LangRAG 与外部 Parser 插件搭配使用。对 PDF、表格、多页文档、OCR 或图片描述场景，外部 Parser 通常能带来更好的分块质量和检索效果。

## 配置

### 知识库创建

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `embedding_model_uuid` | 用于文本向量化的 Embedding 模型 | 必填 |
| `index_type` | 索引策略：`chunk`、`parent_child` 或 `qa` | `chunk` |
| `chunk_size` | 每个 chunk 的字符数 | `512` |
| `overlap` | chunk 之间的重叠字符数 | `50` |
| `parent_chunk_size` | 父块大小，仅 `parent_child` 模式使用 | `2048` |
| `child_chunk_size` | 子块大小，仅 `parent_child` 模式使用 | `256` |
| `qa_llm_model_uuid` | 生成问答对所用 LLM，仅 `qa` 模式使用 | 空 |
| `questions_per_chunk` | 每个 chunk 生成的问题数，仅 `qa` 模式使用 | `1` |

### 检索

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `top_k` | 返回结果数量 | `5` |
| `search_type` | 检索模式：`vector`、`full_text` 或 `hybrid` | `vector` |
| `vector_weight` | 混合检索中向量检索权重，`0.0` 为仅关键词，`1.0` 为仅向量 | `0.7` |
| `query_rewrite` | 查询改写策略：`off`、`hyde`、`multi_query` 或 `step_back` | `off` |
| `rewrite_llm_model_uuid` | 查询改写所用 LLM，启用改写时使用 | 空 |
| `rerank` | 重排序策略：`off`、`rerank_model` 或 `llm` | `off` |
| `rerank_model_uuid` | LangBot rerank 模型，用于候选结果重排 | 空 |
| `rerank_llm_model_uuid` | 用于 LLM 重排序的模型 | 空 |
| `context_window` | 为每个命中结果追加的相邻 chunk 数量 | `0` |

## 索引策略

- **chunk**：默认平面分块。将文档切分为固定大小的 chunk，并直接对每个 chunk 做 embedding。如果 Parser 提供了 sections，则按 section 边界分块，避免把结构化文档完全拍平。
- **parent_child**：父子两级分块。先切分为较大的父块，再切分为较小的子块；对子块做 embedding，检索命中后返回父块文本以提供更完整上下文。有 sections 时会优先把 section 作为天然父块边界。
- **qa**：LLM 生成问答对。先切分文本，再用 LLM 为每个 chunk 生成问答对，并对问题做 embedding。适合用户查询更接近问题表达、原文较长或答案分散的场景。

## 查询改写

- **hyde**：Hypothetical Document Embedding。先让 LLM 为查询生成一个假设性回答，再对该回答做 embedding 用于检索。
- **multi_query**：生成 3 个查询变体，分别检索后按分数合并结果。
- **step_back**：生成一个更抽象的问题，同时使用原始查询和抽象查询检索。

查询改写会增加 LLM 调用成本，建议在召回不足、用户问题表达不稳定或知识库内容较复杂时开启。

## 与 GeneralParsers 搭配使用

GeneralParsers 是当前推荐与 LangRAG 搭配使用的 Parser 插件，因为它可以提供：

- 更干净的 PDF 文本提取
- 结构化 sections
- 保留表格结构的文本
- 文档级 metadata
- 可选的视觉模型 OCR 和图片描述

LangRAG 在摄入时会直接使用这些 Parser 输出。相比仅使用内置 fallback parser，这通常能得到更好的 chunk 结构、更准确的检索结果和更清晰的引用上下文。

## 可观测性页面

LangRAG 提供名为 **Observability** 的 WebUI 页面，用于查看最近的摄入、检索、删除和 embedding 事件，以及面向生产环境的诊断信息：

- 1 分钟、5 分钟、1 小时窗口内的操作量、速率、错误率和零结果率
- 平均延迟以及 p50 / p95 / p99 / max 延迟
- 摄入和检索阶段耗时，包括 parser、chunking、embedding、vector search、rerank、context expansion、vector upsert 等阶段
- 检索质量信号，包括零结果率、Top-K 填充率、引用覆盖率、rerank 使用情况和过滤查询比例
- 活跃告警，包括高错误率、检索零结果过高、p95 延迟过高、持久化异常等
- 隐私友好的事件数据：不会存储原始 query 文本；query、document、collection 标识会尽量使用 hash 表示

近期诊断数据通过 SDK 的安装隔离存储保存，插件重启后仍可保留。历史记录最多保留 100 条事件、192 KiB，仅用于诊断，不作为计费或审计账本。本版本不读取旧的本地 JSONL 历史，`LANGRAG_OBSERVABILITY_DIR` 不再生效；知识文档和向量不受影响。

页面后端还通过 LangBot Page API 暴露 `/snapshot`、`/export`、`/clear` 和 `/metrics`。其中 `/metrics` 返回 Prometheus text format，便于接入外部监控系统。

## 开发

```bash
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中配置 `DEBUG_RUNTIME_WS_URL` 和 `PLUGIN_DEBUG_KEY`，然后使用 IDE 调试器启动。

### 测试

```bash
python3 -m unittest discover -s tests
```

### 离线 Benchmark

```bash
python3 -m benchmarks.run
```

Benchmark 数据集、实验配置、确定性本地适配器和指标代码位于 `benchmarks/`。运行结果会写入 `benchmarks/runs/` 下可追踪的 `results.json` 文件。

可以使用本仓库的 `misc/GeneralParsers` 对 Parser 集成效果做 benchmark：

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/parser_compare_zh.json \
  --config benchmarks/configs/parser_compare.json
```

也可以运行更难的多跳检索用例：

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/hard_multihop_zh.json \
  --config benchmarks/configs/hard_retrieval.json
```

## 链接

- [LangBot 文档](https://langbot.app/docs/)

## 参与贡献

欢迎提交 issue、pull request、文档改进和使用反馈。如果这个插件对你有帮助，也欢迎为仓库点 star。

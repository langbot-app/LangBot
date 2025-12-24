# RAG 混合检索与重排序配置示例

## 核心配置说明

### 1. 向量数据库配置（vdb 部分）

```yaml
# 单数据库（向后兼容）
vdb:
  use: seekdb

# 多数据库（新增）
vdb:
  databases: [chroma, seekdb]
```

### 2. 检索策略配置（rag.retrieval 部分）

```yaml
rag:
  retrieval:
    providers:
      - type: vector    # 向量检索
        vdb: default
      - type: fulltext  # 全文检索（仅 SeekDB 支持）
        vdb: default
      - type: hybrid    # 混合检索（仅 SeekDB 支持）
        vdb: default
```

**不配置时**：自动检测 VDB 能力，SeekDB 会自动使用 hybrid，其他使用 vector

### 3. 重排序配置（rag.rerank 部分）

```yaml
rag:
  rerank:
    type: qwen
    key: sk-your-api-key
    model: qwen3-rerank
```

**不配置时**：使用简单重排序（仅去重）

---

## 配置示例

### 场景 1: SeekDB 混合检索 + Qwen 重排序（推荐）

```yaml
vdb:
  use: seekdb
  seekdb:
    mode: embedded
    path: ./data/seekdb
    database: langbot

rag:
  retrieval:
    providers:
      - type: hybrid
        vdb: default
  rerank:
    type: qwen
    key: sk-your-dashscope-api-key
    model: qwen3-rerank
```

### 场景 2: 自动检测（零配置）

```yaml
vdb:
  use: seekdb
  seekdb:
    mode: embedded
    path: ./data/seekdb

# 不配置 rag 部分，自动使用：
# - 混合检索（SeekDB 支持）
# - 简单重排序
```

### 场景 3: 多数据库 RRF 融合

```yaml
vdb:
  databases: [chroma, seekdb]
  chroma: {}
  seekdb:
    mode: embedded
    path: ./data/seekdb

rag:
  retrieval:
    providers:
      - type: vector
        vdb: chroma
      - type: fulltext
        vdb: seekdb
  rerank:
    type: qwen
    key: sk-your-api-key
    model: qwen3-rerank
```

### 场景 4: 纯向量检索（传统模式）

```yaml
vdb:
  use: chroma
  chroma: {}

# 不配置 rag，自动使用纯向量检索
```

---

## 关键变更

1. **新增模块**：`src/langbot/pkg/rag/retrieval/` 和 `src/langbot/pkg/rag/rerank/`
2. **VectorDBManager**：支持多实例（`ap.vector_db_mgr.get_default_db()`）
3. **SeekDB**：新增 `search_fulltext()` 和 `search_hybrid()` 方法
4. **完全向后兼容**：不修改配置即可使用

---

## Qwen API Key 获取

https://dashscope.console.aliyun.com/ → 创建 API Key

---

## 查看日志验证

```bash
# 查看检索策略
grep "Auto-configured\|Configured provider" logs/langbot.log

# 查看重排序
grep "rerank" logs/langbot.log
```

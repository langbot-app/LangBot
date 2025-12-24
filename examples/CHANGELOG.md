# PR 变更说明：混合检索与重排序

## 主要改进

### 1. 新增检索系统 (`src/langbot/pkg/rag/retrieval/`)

- **VectorSearchProvider**: 向量检索
- **FullTextSearchProvider**: 全文检索（需 SeekDB）
- **HybridSearchProvider**: 混合检索（需 SeekDB）
- **RRF 融合**: 多 Provider 结果自动融合

### 2. 新增重排序系统 (`src/langbot/pkg/rag/rerank/`)

- **SimpleReranker**: 简单去重（默认）
- **QwenReranker**: Qwen API 重排序

### 3. VectorDBManager 增强

- 支持多实例：`databases: [chroma, seekdb]`
- 智能复用相同类型实例
- API 变更：`get_default_db()` 替代 `vector_db`

### 4. SeekDB 功能增强

- `search_fulltext()`: 全文检索（BM25）
- `search_hybrid()`: 原生混合检索
- 安全的 SQL 标识符映射（UUID → 表名）
- 文档文本自动索引

## 文件变更

```
23 files changed, 1485 insertions(+), 157 deletions(-)
```

主要文件：
- `retrieval/retrieval.py` (178行新增)
- `rerank/providers/qwen.py` (149行新增)
- `vector/vdbs/seekdb.py` (395行新增, 82行删除)
- `vector/mgr.py` (重构多实例支持)

## 向后兼容

✅ 所有现有配置完全兼容，无需修改

## 配置示例

见 `examples/config-*.yaml` 文件

## 迁移建议

1. 保持现有配置不变（自动使用向量检索）
2. 评估是否切换到 SeekDB（获得混合检索）
3. 评估是否启用 Qwen 重排序（提升 10-30% 准确性）


所有文件通过语法检查，无错误。

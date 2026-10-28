# TavilySearch 插件

一个为 LangBot 提供搜索功能的插件，使用专为 AI 代理（LLM）构建的 Tavily API 搜索引擎。

## 功能特性

- 由 Tavily 提供支持的实时网页搜索
- 支持不同的搜索深度（基础/高级）
- 主题特定搜索（通用/新闻/财经）
- 包含 AI 生成的答案
- 包含相关图片
- 包含原始 HTML 内容
- 可自定义结果数量

## 安装

1. 安装插件。

2. 配置您的 Tavily API 密钥：
   - 从 [Tavily](https://tavily.com/) 获取您的 API 密钥
   - 在 LangBot 的插件配置中添加 API 密钥

## 使用方法

此插件添加了一个 `tavily_search` 工具，可在对话中被 LLM 使用。

### 参数

- **query**（必需）：搜索查询字符串
- **search_depth**（可选）："basic"（默认）或 "advanced"
- **topic**（可选）："general"（默认）、"news" 或 "finance"
- **max_results**（可选）：结果数量（1-20，默认：5）
- **include_answer**（可选）：包含 AI 生成的答案（默认：false）
- **include_images**（可选）：包含相关图片（默认：false）
- **include_raw_content**（可选）：包含原始 HTML 内容（默认：false）

### 示例

当与您的 LangBot 聊天时，LLM 可以自动使用此工具：

```
用户：人工智能的最新新闻是什么？

机器人：[使用 tavily_search 工具，参数 topic="news"]
```

## 开发

开发或修改此插件：

1. 在 `components/tools/tavily_search.py` 中编辑工具逻辑
2. 在 `manifest.yaml` 中修改配置
3. 在 `components/tools/tavily_search.yaml` 中更新工具参数

## 配置

插件需要以下配置：

- **tavily_api_key**：您的 Tavily API 密钥（必需）

## 许可证

此插件是 LangBot 插件生态系统的一部分。

## 链接

- [Tavily API 文档](https://docs.tavily.com/)
- [LangBot 文档](https://langbot.app/docs/)


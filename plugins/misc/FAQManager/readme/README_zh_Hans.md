# FAQ 管理器

通过 LangBot WebUI 中的可视化页面管理常见问答条目，并让 LLM 在对话中自动检索它们。

## 功能

- **Page 组件**：在侧边栏「插件扩展页」中提供完整的增删改查界面，用于管理问答对。
- **Tool 组件**：`search_faq` — 让 LLM 通过关键词搜索 FAQ 数据库，将匹配的条目返回给用户。
- **持久化存储**：FAQ 条目通过插件存储保存，重启后不会丢失。
- **多语言**：管理页面支持英文、简体中文和日语。
- **暗色模式**：页面自动适配 LangBot 主题。

## 组件

| 组件 | 类型 | 说明 |
|------|------|------|
| `components/pages/manager/` | Page | FAQ 管理界面（增删改查、搜索） |
| `components/tools/search_faq.py` | Tool | FAQ 条目关键词搜索，供 LLM 调用 |
| `components/event_listener/default.py` | EventListener | 默认事件监听器（占位） |

## 使用方法

1. 在 LangBot 中安装本插件。
2. 在侧边栏找到 **插件扩展页**，选择 **FAQ 管理**。
3. 通过页面添加问答对。
4. 当用户在对话中提问时，LLM 会通过 `search_faq` 工具查找匹配的 FAQ 条目并据此回答。

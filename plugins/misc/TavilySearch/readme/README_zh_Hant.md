# TavilySearch 插件

一個 [LangBot](https://github.com/langbot-app/langbot) 插件，使用 Tavily API 提供搜尋功能。Tavily 是專為 AI 代理 (LLMs) 構建的搜尋引擎。

## 功能

- 由 Tavily 提供支援的即時網頁搜尋
- 支援不同的搜尋深度（basic/advanced）
- 特定主題搜尋（general/news/finance）
- 包含 AI 生成的回答
- 包含相關圖片
- 包含原始 HTML 內容
- 可自定義結果數量

## 安裝

1. 安裝插件。

2. 設定您的 Tavily API 金鑰：
   - 從 [Tavily](https://tavily.com/) 獲取您的 API 金鑰
   - 將 API 金鑰添加到 LangBot 的插件設定中

## 使用方法

此插件添加了一個 `tavily_search` 工具，可供 LLM 在對話中使用。

### 參數

- **query** (必填): 搜尋查詢字串
- **search_depth** (選填): "basic" (預設) 或 "advanced"
- **topic** (選填): "general" (預設), "news", 或 "finance"
- **max_results** (選填): 結果數量 (1-20, 預設: 5)
- **include_answer** (選填): 包含 AI 生成的回答 (預設: false)
- **include_images** (選填): 包含相關圖片 (預設: false)
- **include_raw_content** (選填): 包含原始 HTML 內容 (預設: false)

### 範例

與您的 LangBot 聊天時，LLM 可以自動使用此工具：

```
使用者: 關於人工智能的最新消息是什麼？

機器人: [使用 tavily_search 工具，主題為 "news"]
```

## 開發

如需開發或修改此插件：

1. 在 `components/tools/tavily_search.py` 中編輯工具邏輯
2. 在 `manifest.yaml` 中修改設定
3. 在 `components/tools/tavily_search.yaml` 中更新工具參數

## 設定

此插件需要以下設定：

- **tavily_api_key**: 您的 Tavily API 金鑰 (必填)

## 授權

此插件是 LangBot 插件生態系統的一部分。

## 相關連結

- [Tavily API 文檔](https://docs.tavily.com/)
- [LangBot 文檔](https://langbot.app/docs/)

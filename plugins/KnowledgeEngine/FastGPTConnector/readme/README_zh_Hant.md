# FastGPTConnector

使用 FastGPT API 從 FastGPT 知識庫中檢索知識。

## 關於 FastGPT

FastGPT 是一個基於 LLM 模型的開源知識庫問答系統。它為複雜的問答場景提供開箱即用的數據處理和模型調用能力。

## 功能特性

- 從 FastGPT 數據集/知識庫中搜尋並檢索知識
- 支援多種搜尋模式（向量檢索、全文檢索、混合檢索）
- 可配置相似度閾值和 Token 限制
- 可選重排序（Re-ranking）以獲得更好結果
- 使用擴展模型進行查詢優化

## 配置說明

此插件需要以下配置參數：

### 必要參數

- **api_base_url**: FastGPT API 的基礎 URL
  - 本地部署：`http://localhost:3000`（預設值）
  - 遠端伺服器：您的伺服器 URL（例如：`https://your-domain.com`）
- **api_key**: 您的 FastGPT API 金鑰
  - 格式：`fastgpt-xxxxx`
- **dataset_id**: 您的 FastGPT 知識庫/數據集 ID

### 可選參數

- **limit**（預設值：5000）：檢索的最大 Token 數量
- **similarity**（預設值：0.0）：最低相似度分數 (0-1)
- **search_mode**（預設值：embedding）：使用的搜尋方法
  - `embedding`: 語義向量搜尋
  - `fullTextRecall`: 全文關鍵字搜尋
  - `mixedRecall`: 結合兩種方法的混合搜尋
- **using_rerank**（預設值：false）：是否使用重排序
- **dataset_search_using_extension_query**（預設值：false）：是否使用查詢優化
- **dataset_search_extension_model**（可選）：用於查詢優化的模型
- **dataset_search_extension_bg**（可選）：查詢優化的背景描述

## 如何獲取配置值

### 獲取您的 FastGPT API 金鑰

1. 訪問您的 FastGPT 實例（例如：`http://localhost:3000`）
2. 導航至 API 管理或設置部分
3. 創建或複製您的 API 金鑰（格式：`fastgpt-xxxxx`）

### 獲取您的數據集 ID

1. 在 FastGPT 中，前往您的知識庫列表
2. 點擊某個知識庫以查看其詳情
3. 可以在 URL 或數據集詳情頁面中找到數據集 ID

## API 參考

此插件使用 FastGPT 數據集搜尋測試 API：
- 端點：`POST /api/core/dataset/searchTest`
- 文檔：https://doc.fastgpt.io/docs/introduction/development/openapi/dataset

## 搜尋方法

### 向量檢索 (Embedding Search)
使用基於向量嵌入的語義相似度。最適合理解查詢意圖並查找語義相關的內容。

### 全文檢索 (Full-Text Recall)
傳統的基於關鍵字的全文搜尋。最適合查找精確匹配和特定術語。

### 混合檢索 (Mixed Recall)
結合向量檢索和全文檢索方法。提供語義理解和關鍵字匹配平衡的結果。

# DifyDatasets連接器

使用 Dify API 從 Dify 知識庫檢索知識或將文件儲存到 Dify 知識庫中。

＃＃ 配置

請在 LangBot 中新增外部知識庫，並選擇「DifyDatasetsConnector」作為知識擷取器類型。

### 建立設定（建立知識庫時設定）

-**api_base_url**：Dify API 的基本 URL
  - 對於 Dify Cloud：「https://api.dify.ai/v1」（預設）
  - 對於自架執行個體：您的伺服器 URL（例如「http://localhost/api」或「https://your-domain.com/api」）
-**dify_apikey**：您的 Dify 實例中的 Dify API 金鑰
-**dataset_id**：您的 Dify 知識庫/資料集的 ID

### 檢索設定（每個查詢均可調整）

-**search_method**（預設值：semantic_search）：要使用的搜尋方法
  -`keyword_search`：基於關鍵字的搜索
  -`semantic_search`：語意相似性搜尋（預設）
  -`full_text_search`：全文搜尋
  -`hybrid_search`：結合語意和全文的混合搜尋
-**top_k**（預設值：5）：檢索結果的最大數量
-**score_threshold_enabled**(預設: false): 是否啟用分數閾值過濾
-**score_threshold**（預設值：0.5）：最小相關性分數（0-1），僅在啟用分數閾值時顯示
-**reranking_enable**（預設值：false）：啟用重新排名以提高結果品質。重新排名模型會自動從您​​的 Dify 資料集設定中取得 - 請先在 Dify 控制台中設定重新排名模型

## 如何取得設定值

### 取得您的 Dify API 金鑰

1. 造訪https://cloud.dify.ai/
2. 導覽至您的知識庫頁面
3. 點選左側邊欄中的“API 存取”
4. 從「API 金鑰」部分建立或複製您的 API 金鑰

### 取得您的資料集 ID

1. 在 Dify 知識庫清單中，按一下您的知識庫
2. 資料集 ID 在 URL 中：`https://cloud.dify.ai/datasets/{dataset_id}`
3.或者您可以在知識庫的API文檔頁面中找到它

### 配置重新排名

1. 在 Dify 控制台中，前往您的資料集設置
2. 啟用重新排名並選擇重新排名模型（例如“cohere/rerank-v3.5”）
3. 儲存設定
4. 在 LangBot 中，啟用「啟用重新排名」開關 - 外掛程式將自動使用 Dify 中配置的模型

## API 參考

該外掛程式使用 Dify 資料集 API：
- 檢索：`POST /v1/datasets/{dataset_id}/retrieve`
- 資料集資訊：`GET /v1/datasets/{dataset_id}`
- 文件上傳：`POST /v1/datasets/{dataset_id}/document/create-by-file`
- 文件刪除：`DELETE /v1/datasets/{dataset_id}/documents/{document_id}`
- 文件：https://docs.dify.ai/

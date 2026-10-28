# RAGFlow連接器

使用 RAGFlow API 從 RAGFlow 知識庫檢索知識或將檔案儲存到 RAGFlow 知識庫中。

## 關於 RAGFlow

RAGFlow 是一個基於深度文件理解的開源 RAG（檢索增強生成）引擎。它提供了真實的問答能力，以及來自各種複雜格式數據的有根據的引用。

＃＃ 特徵

- 從 RAGFlow 資料集/知識庫檢索知識塊
- 透過自動解析將檔案上傳並擷取至 RAGFlow 資料集中
- 支援單一查詢中的多個資料集
- 可配置的相似度閾值和向量權重
- 結合關鍵字和向量相似度的混合搜尋
- 攝取後自動觸發GraphRAG知識圖構建
- 攝取後自動觸發 RAPTOR 分層匯總
- 知識庫建立時的資料集 ID 驗證
- 傳回具有豐富元資料的結果，包括術語和向量相似度分數

＃＃ 配置

該插件需要以下配置參數：

### 所需參數（建立設定）

-**api_base_url**：RAGFlow API 的基本 URL
  - 針對本機部署：`http://localhost:9380`（預設）
  - 對於遠端伺服器：您的伺服器 URL（例如“http://your-domain.com:9380”）
-**api_key**：來自 RAGFlow 實例的 RAGFlow API 金鑰
-**dataset_ids**：要搜尋的以逗號分隔的資料集 ID
  - 格式：`"dataset_id1,dataset_id2,dataset_id3"`
  - 例：`“b2a62730759d11ef987d0242ac120004，a3b52830859d11ef887d0242ac120005”`

### 可選參數（建立設定）

-**auto_graphrag**（預設：false）：檔案攝取後自動觸發GraphRAG知識圖構建
-**auto_raptor**（預設：false）：檔案攝取後自動觸發 RAPTOR 分層匯總

### 可選參數（檢索設定）

-**top_k**（預設值：1024）：檢索結果的最大數量
-**similarity_threshold**（預設值：0.2）：最小相似度分數（0-1）
-**vector_similarity_weight**（預設值：0.3）：混合搜尋中向量相似度的權重（0-1）
-**page_size**（預設值：30）：每頁結果數
-**keyword**（預設值：false）：使用LLM從查詢中提取關鍵字以增強檢索
-**rerank_id**：RAGFlow 中配置的重新排序模型 ID（例如「BAAI/bge-reranker-v2-m3」）
-**use_kg**（預設：false）：啟用知識圖譜檢索

## 如何取得設定值

### 取得您的 RAGFlow API 金鑰

1. 存取您的 RAGFlow 執行個體（例如「http://localhost:9380」）
2. 導覽至**使用者設定**>**API**部分
3. 產生或複製您的 API 金鑰（格式：`ragflow-xxxxx`）

### 取得您的資料集 ID

1. 在 RAGFlow 中，前往您的知識庫/資料集列表
2. 點擊資料集查看其詳細信息
3. 資料集ID通常顯示在URL或資料集詳細資料中
4. 對於多個資料集，收集所有ID並用逗號連接

## API 參考

該插件使用以下 RAGFlow API：
- 檢索：`POST /api/v1/retrieval`
- 上傳文件：`POST /api/v1/datasets/{dataset_id}/documents`
- 解析文件：`POST /api/v1/datasets/{dataset_id}/chunks`
- 刪除文件：`DELETE /api/v1/datasets/{dataset_id}/documents`
- GraphRAG 建構：`POST /api/v1/datasets/{dataset_id}/run_graphrag`
- RAPTOR 建構：`POST /api/v1/datasets/{dataset_id}/run_raptor`
- 列出資料集（驗證）：`GET /api/v1/datasets`
- 文件：https://ragflow.io/docs/dev/http_api_reference

## 檢索方法

RAGFlow 採用混合檢索方法：
-**關鍵字相似度**：傳統的基於關鍵字的匹配
-**向量相似度**：使用嵌入的語意相似度
-**加權組合**：將兩種方法與可配置權重結合
-**知識圖譜**：可選的基於圖的檢索，用於關係感知答案
-**重新排名**：可選的重新排名模型，以提高結果質量

“vector_similarity_weight”參數控制關鍵字和向量方法之間的平衡。

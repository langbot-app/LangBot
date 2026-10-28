# GeneralParsers

LangBot 官方解析器插件，為知識引擎插件（如 LangRAG）從文件中提取結構化文本。

## 支援格式

| 格式 | MIME 類型 | 解析器 |
|------|-----------|--------|
| PDF | `application/pdf` | 基於 PyMuPDF 的佈局感知提取，包含表格、頁面標記和可選的視覺增強 |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 使用 python-docx 提取段落/表格，並支援可選的嵌入圖像識別 |
| Markdown | `text/markdown` | 轉換為 HTML 後進行結構化提取（標題、列表、程式碼塊、表格） |
| HTML | `text/html` | BeautifulSoup 提取（自動移除腳本/樣式） |
| TXT | `text/plain` | 自動編碼檢測 (chardet) |
| 圖像 | `image/png`, `image/jpeg`, `image/webp`, `image/gif`, `image/bmp`, `image/tiff` | 配置視覺模型後直接進行基於視覺的識別 |

## 架構設計

```
┌──────────────────────────────────────────────┐
│  KnowledgeEngine Plugin (例如 LangRAG)       │
│  分塊 → 向量化 → 存儲 → 檢索                │
└──────────────────┬───────────────────────────┘
                   │ invoke_parser (RPC)
┌──────────────────▼───────────────────────────┐
│          GeneralParsers                      │
│                                              │
│  文件字節 → 格式檢測 → 解析                 │
│                                              │
│  解析結果 (ParseResult):                     │
│    ├── text: 提取的完整文本                  │
│    ├── sections: 按標題分割的章節            │
│    │   └── TextSection(內容, 標題,           │
│    │                   層級)                 │
│    └── metadata: 文件名, MIME 類型等         │
└──────────────────────────────────────────────┘
```

## 功能特性

- **可選視覺模型支持** - 配置具有視覺能力的 LLM 以對掃描版 PDF 頁面進行 OCR、識別 PDF/DOCX 嵌入圖像以及解析直接上傳的圖像。
- **改進的 PDF 解析** - 基於 PyMuPDF 的提取保留了頁面邊界，將表格合併到輸出中，並提供更豐富的文件元數據。
- **掃描版 PDF 處理** - 自動檢測疑似掃描頁面，並在配置後使用視覺模型進行 OCR。
- **跨格式圖像識別** - 嵌入在 PDF/DOCX 中的圖像和直接上傳的圖像可以轉換為內聯識別文本，供下游檢索使用。
- **頁眉/頁腳過濾** - 自動檢測並從 PDF 輸出中移除重複的頁眉和頁腳。
- **章節結構識別** - 檢測 Markdown 風格標題 (`# ~ ######`) 並將輸出拆分為帶層級的章節。
- **表格轉 Markdown** - PDF/HTML/Markdown 中的表格會被轉換為 Markdown 表格格式。
- **異步解析** - 文件解析在線程池中運行，避免阻塞事件循環。
- **自動編碼檢測** - 使用 chardet 進行編碼檢測，支持 GBK、UTF-8 等。
- **格式回退** - 不支持的格式會自動嘗試作為純文本解析。

## 配置說明

該插件提供一個可選配置項：

- `vision_llm_model_uuid`: 用於掃描頁面 OCR、PDF/DOCX 嵌入圖像識別和直接圖像解析的具有視覺能力的 LLM 模型 UUID。

如果此項留空，GeneralParsers 仍可正常工作，但圖像識別將回退到佔位符，且 PDF 解析僅使用文本/佈局提取。

## 使用方法

1. 在 LangBot 中安裝此插件。
2. 如果您需要掃描版 PDF 的 OCR、DOCX/PDF 圖像識別或直接圖像解析，請配置視覺模型。
3. 向知識庫上傳文件時，選擇 GeneralParsers 作為解析器。
4. 解析結果會自動傳遞給 KnowledgeEngine 插件進行進一步處理。

## 輸出結構

GeneralParsers 返回一個結構化的 `ParseResult`，包含：

- `text`: 提取的完整文本
- `sections`: 感知標題的文本章節，適用於偏好結構化數據的分塊策略
- `metadata`: 文件元數據，如文件名、MIME 類型、頁數、表格存在情況、掃描頁面標記及視覺使用統計。

最新的 PDF 解析器元數據包含以下欄位：

- `page_count` (頁數)
- `word_count` (字數)
- `has_tables` (包含表格)
- `has_scanned_pages` (包含掃描頁面)
- `headers_footers_removed` (已移除頁眉頁腳)
- `vision_used` (是否使用了視覺能力)
- `vision_tasks_count` (視覺任務數)
- `vision_scanned_pages_count` (視覺掃描頁面數)
- `vision_images_described_count` (視覺描述圖像數)

## 開發

```bash
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中配置 `DEBUG_RUNTIME_WS_URL` 和 `PLUGIN_DEBUG_KEY`，然後使用您的 IDE 調試器啟動。

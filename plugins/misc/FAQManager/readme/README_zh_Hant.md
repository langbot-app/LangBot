# FAQ 管理器

透過 LangBot WebUI 中的視覺化頁面管理常見問答條目，並讓 LLM 在對話中自動檢索它們。

## 功能

- **Page 元件**：在側邊欄「插件擴展頁」中提供完整的增刪改查介面，用於管理問答對。
- **Tool 元件**：`search_faq` — 讓 LLM 透過關鍵字搜尋 FAQ 資料庫，將匹配的條目回傳給使用者。
- **持久化儲存**：FAQ 條目透過插件儲存保存，重新啟動後不會遺失。
- **多語言**：管理頁面支援英文、簡體中文和日語。
- **暗色模式**：頁面自動適配 LangBot 主題。

## 元件

| 元件 | 類型 | 說明 |
|------|------|------|
| `components/pages/manager/` | Page | FAQ 管理介面（增刪改查、搜尋） |
| `components/tools/search_faq.py` | Tool | FAQ 條目關鍵字搜尋，供 LLM 呼叫 |
| `components/event_listener/default.py` | EventListener | 預設事件監聽器（佔位） |

## 使用方法

1. 在 LangBot 中安裝本插件。
2. 在側邊欄找到 **插件擴展頁**，選擇 **FAQ 管理**。
3. 透過頁面新增問答對。
4. 當使用者在對話中提問時，LLM 會透過 `search_faq` 工具查詢匹配的 FAQ 條目並據此回答。

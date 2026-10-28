# AI 圖片生成插件

＃＃ 介紹

相容於OpenAI影像產生API格式的繪圖插件。支援與OpenAI影像產生API相容的任何服務。

＃＃ 特徵

- ✅ 完全相容OpenAI映像產生API格式
- 🎨 支援自訂 API 端點和模型名稱
- 📐支援多種影像長寬比
- 🔧 靈活的配置選項

## 設定指南

### API配置

-**API端點**：預設為`https://api.qhaigc.net`，可以客製化為任何相容的OpenAI風格的API端點
-**API金鑰**：從[https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)取得您的API金鑰
-**模型名稱**：您可以設定自訂模型名稱，預設為`qh-draw-x1-pro`

### 圖片大小選項

支援以下圖像尺寸：

- 方形 1:1 (1024x1024)
- 方 1:1 (1280x1280)
- 肖像 3:5 (768x1280)
- 風景 5:3 (1280x768)
- 肖像 9:16 (720x1280)
- 風景 16:9 (1280x720)
- 風景 4:3 (1024x768)
- 肖像 3:4 (768x1024)

＃＃ 用法

使用`!draw`指令產生圖像：

```bash
# Generate an image
!draw a beautiful sunset landscape
!draw a cat sitting on a rainbow
```

## 安裝步驟

1.從LangBot插件管理頁面安裝此外掛
2. 取得您的API金鑰：[https://api.qhaigc.net/console/token](https://api.qhaigc.net/console/token)
3.在插件配置中填寫API Key
4.（可選）配置API端點、模型名稱和預設映像大小

## 支援的型號

###奈米香蕉系列

-**Nano Banana 1**（2025 年 8 月發布）：Google DeepMind 的圖像生成模型，基於 Gemini 2.5 Flash 架構，具有 450M 至 8B 參數。核心優勢是角色一致性、多影像融合和本地編輯。它以 1362 分領先 LMArena 影像編輯排行榜，廣泛應用於電子商務、設計、教育等領域。

-**Nano Banana 2**（2025年11月發布）：第一代的全面升級，支援原生2K分辨率，可選4K超分辨率。生成速度提升300%，僅需10秒即可實現複雜場景。在中文文字渲染和數學公式推導方面取得重大突破。它理解物理邏輯和世界知識，採用「認知+生成」混合架構，徹底改變創意產業的生產力。

###啟航AI繪畫系列

-**qh-draw-3d**：專注於產生流行的3D風格影像，特點是3D模型細膩，3D視覺效果強烈。
-**qh-draw-4d**：專注於產生流行的 4D 風格影像，具有複雜的 4D 模型和接近現實但不是實際照片的視覺效果。
-**qh-draw-x1-pro**：啟航AI Drawing x1-pro模型，基於具有自然語言理解能力的開源SD模型。
-**qh-draw-x2-preview**：自主開發的專業繪圖模型V2.0。在x1-pro的基礎上，增強了語言理解和綜合繪圖能力，使其適合更多任務。
-**qh-draw:Korean-comic-style**：專門產生經典的2D韓漫風格圖像，具有明亮的色彩、流暢的線條和精確的韓漫場景情緒。

### 可用型號列表

`nano-banana-1`、`nano-banana-2`、`qh-draw-3d`、`qh-draw-4d`、`qh-draw-x1-pro`、`qh-draw-x2-preview`、`qh-draw:韓國漫畫風格`

## 相容性

該插件相容於任何遵循OpenAI圖像生成API規範的服務，包括但不限於：

- OpenAI DALL-E 3
- 相容OpenAI格式的其他影像產生服務

＃＃ 執照

我的許可證

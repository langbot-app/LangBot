# 調度通知

使用自然語言安排通知

＃＃ 特徵

ScheNotify是一個LangBot插件，允許使用者透過與LLM的自然語言互動來設定定時提醒。

### 主要特點

-**自然語言互動**：透過LLM了解使用者的調度意圖
-**智慧時間解析**：自動取得目前時間並計算提醒時間
-**多語言支援**：支援中英文提醒訊息
-**日程管理指令**：檢視和刪除預定提醒
-**自動通知**：在預定時間自動發送提醒訊息

＃＃ 配置

### 語言設定

您可以在外掛程式配置中選擇提醒訊息的語言：

-`zh_Hans`（簡體中文）- 默認
-`en_US`（英語）

＃＃ 用法

### 1. 透過LLM安排

只需用自然語言告訴法學碩士您的日程安排：

**範例：**
```
Remind me to have a meeting at 3 PM tomorrow
Remind me to submit the report at 9 AM the day after tomorrow
Remind me to have lunch at 12 PM next Monday
Remind me about Christmas dinner at 2024-12-25 18:00
```

法學碩士將自動：
1. 呼叫`get_current_time_str`取得目前時間
2. 解析您的時間表達式並轉換為標準格式
3. 呼叫`schedule_notify`建立提醒

### 2.查看預定提醒

使用指令查看所有預定提醒：

```
!sche
```

輸出範例：
```
[Notify] Scheduled reminders:
#1 2024-12-25 18:00:00: Christmas dinner
#2 2024-12-26 09:00:00: Submit report
```

### 3.刪除提醒

使用指令刪除特定提醒（使用「!sche」中的數字）：

```
!dsche i <number>
```

例子：
```
!dsche i 1   # Delete the 1st reminder
```

＃＃ 成分

＃＃＃ 工具

1.**get_current_time_str**- 取得當前時間
   - 回傳格式：`YYYY-MM-DD HH:MM:SS`
   - LLM在設定提醒之前必須呼叫此工具

2.**schedule_notify**- 安排通知
   - 參數：時間字串、提醒訊息
   - 自動從Tool的session參數中取得session信息

### 指令

1.**sche**（別名：s）-列出所有預定的提醒
2.**dsche**（別名：d）-刪除指定提醒

## 技術細節

- 檢查間隔：每 60 秒一次
- 時間精確度：分鐘級（每分鐘檢查一次）
- 會話資訊：透過Tool的會話參數自動取得
- 持久性：目前使用記憶體儲存（重新啟動時遺失）

## 對話範例

**使用者：**提醒我明天下午 2 點參加會議

**法學碩士：**當然，我會為您設定提醒。

*[LLM呼叫get_current_time_str]*
*[LLM呼叫schedule_notify(time_str="2024-12-26 14:00:00", message="參加會議")]*

**法學碩士：**完成！我會在2024-12-26 14:00:00提醒您：參加會議

*[第二天下午 2 點]*

**機器人：**[通知]參加會議

## 註釋

- 提醒時間必須是未來的，過去的時間將被拒絕
- 提醒訊息將發送到設定提醒的相同會話
- 插件重新啟動後未發送的提醒將會遺失（後續版本將支援持久化）

## 開發者訊息

- 作者：RockChinQ
- 版本：0.2.0
- 插件類型：LangBot 插件 v1

＃＃ 執照

LangBot 插件生態系的一部分。

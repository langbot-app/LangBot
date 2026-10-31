# MCBotPlugin

為 Minecraft 伺服器群提供服務的 LangBot 外掛：將伺服器綁定到聊天群、查詢伺服器即時狀態與線上玩家、統計每位玩家的線上時長。

> 這是舊版 [MCBotPlugin](https://github.com/langbot-app/MCBotPlugin)（基於 QChatGPT）遷移到新版 LangBot 外掛 SDK 的版本。儲存由 MongoDB 改為外掛內建 KV 儲存（無需任何外部資料庫），Minecraft 狀態查詢由同步 `mctools` 改為非同步 `mcstatus`，背景時長取樣由執行緒改為 asyncio 任務。

## 功能

- **綁定伺服器**：每個群可綁定一個 Minecraft（Java 版）伺服器
- **狀態查詢**：即時檢視 MOTD、版本、線上人數與玩家名單
- **時長統計**：背景定時取樣線上玩家，統計任意時段內每位玩家的線上時長

## 指令

| 指令 | 說明 | 權限 |
| --- | --- | --- |
| `!mcbot` | 檢視說明 | 所有人 |
| `!mcbot bind <位址[:連接埠]>` | 綁定伺服器到本群 | 管理員 |
| `!mcbot unbind` | 解綁伺服器 | 管理員 |
| `!mcbot status` | 檢視伺服器狀態與線上玩家 | 所有人 |
| `!mcbot time [分鐘]` | 檢視線上時長統計（預設 1440 分鐘 = 24 小時） | 所有人 |

> 管理員由 LangBot 的 `admins` 設定（`{launcher_type}_{launcher_id}`）決定。

## 設定項

| 設定 | 說明 | 預設 |
| --- | --- | --- |
| `track_interval` | 背景取樣線上玩家的間隔（秒），最小 15 | 60 |
| `ping_timeout` | Ping 伺服器的逾時時間（秒） | 10 |

## 相依套件

- [`mcstatus`](https://github.com/py-mine/mcstatus) —— Minecraft 伺服器狀態查詢

## 資料儲存

綁定關係與線上記錄儲存在 LangBot 外掛內建 KV 儲存中，無需 MongoDB。線上記錄預設保留 14 天。

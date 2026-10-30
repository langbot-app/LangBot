# MCBotPlugin

为 Minecraft 服务器群提供服务的 LangBot 插件：将服务器绑定到聊天群、查询服务器实时状态与在线玩家、统计每位玩家的在线时长。

> 这是旧版 [MCBotPlugin](https://github.com/langbot-app/MCBotPlugin)（基于 QChatGPT）迁移到新版 LangBot 插件 SDK 的版本。存储由 MongoDB 改为插件内置 KV 存储（无需任何外部数据库），Minecraft 状态查询由同步 `mctools` 改为异步 `mcstatus`，后台时长采样由线程改为 asyncio 任务。

## 功能

- **绑定服务器**：每个群可绑定一个 Minecraft（Java 版）服务器
- **状态查询**：实时查看 MOTD、版本、在线人数与玩家名单
- **时长统计**：后台定时采样在线玩家，统计任意时段内每位玩家的在线时长

## 命令

| 命令 | 说明 | 权限 |
| --- | --- | --- |
| `!mcbot` | 查看帮助 | 所有人 |
| `!mcbot bind <地址[:端口]>` | 绑定服务器到本群 | 管理员 |
| `!mcbot unbind` | 解绑服务器 | 管理员 |
| `!mcbot status` | 查看服务器状态与在线玩家 | 所有人 |
| `!mcbot time [分钟]` | 查看在线时长统计（默认 1440 分钟 = 24 小时） | 所有人 |

> 管理员由 LangBot 的 `admins` 配置（`{launcher_type}_{launcher_id}`）决定。

## 配置项

| 配置 | 说明 | 默认 |
| --- | --- | --- |
| `track_interval` | 后台采样在线玩家的间隔（秒），最小 15 | 60 |
| `ping_timeout` | Ping 服务器的超时时间（秒） | 10 |

## 依赖

- [`mcstatus`](https://github.com/py-mine/mcstatus) —— Minecraft 服务器状态查询

## 数据存储

绑定关系与在线记录保存在 LangBot 插件内置 KV 存储中，无需 MongoDB。在线记录默认保留 14 天。

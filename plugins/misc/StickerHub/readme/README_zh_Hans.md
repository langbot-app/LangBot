# StickerHub

[English](../README.md)

LangBot 的无服务器表情包 / 图片图床。图片存放在插件自己的 **plugin storage**
中（按内容寻址，相同图片只存一份），插件为每个表情包返回**稳定 URL**，
人工回复与 AI 回复都可以直接使用。

## 功能

- **无服务器图床**：不依赖外部服务，图片字节存放在插件存储中，目录是一组
  按条记录的元数据，并提供副本写入插件 `assets/stickers/` 目录（见
  `materialize_to_assets`）。
- **稳定 URL**：
  `{public_base_url}/api/v1/plugins/langbot-team/StickerHub/assets/stickers/<slug>-<sha12>.<ext>`。
  文件名由昵称与内容 SHA-256 派生，同一张图每次返回同一地址。LangBot 的 asset
  路由在单 Workspace 部署下公开可访问，因此 IM 平台与 AI 都可以直接拉取。
- **人工回复**：管理 Page（`components/pages/hub/`）支持文件选择、data URL、
  图片 URL 上传，提供画廊、复制地址、删除与清理。
- **AI 回复**：四个 Tool 让模型存取表情包，并以字符串形式返回稳定地址。
- **稳定联动接口**：`stickerhub_get_sticker_url` 是供其它插件调用的稳定契约，
  见[与 HumanTakeover 联动](#与-humantakeover-联动)。
- **按安装隔离**：存储键以 `instance:workspace:installation` 为作用域，多个
  Workspace 共用一个 shared-runtime 对象图时互不可见。
- **存储有界**：超过 `max_stickers` 后淘汰最早的条目；每次写入受
  `max_sticker_mb` 限制。
- **不阻塞 event loop**：远端下载与文件写入放到工作线程，远端响应边流式读取
  边校验大小。

## 配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `public_base_url` | string | `""` | 可选的 LangBot 实例对外基础地址。填写后返回绝对 URL；留空则返回相对的 `/api/v1/plugins/...` 路径。 |
| `max_sticker_mb` | integer | `8` | 超过该大小的图片将被拒绝，与 HumanTakeover 的 8 MiB 预算一致。 |
| `max_stickers` | integer | `2000` | 超过该数量后淘汰最早的表情包，限制存储增长。 |
| `materialize_to_assets` | boolean | `true` | 是否把新表情包同时写入 `assets/stickers/`，以便 asset 路由对外提供访问。 |

## 存储结构

插件存储键统一以安装作用域开头，例如 `sh:<instance>:<workspace>:<installation>:...`。

| 键 | 值 |
|----|----|
| `sh:<scope>:meta:<slug>` | JSON 元数据：slug、名称、mime、ext、大小、SHA-256、文件名、时间戳、来源 |
| `sh:<scope>:blob:<sha256>` | 原始图片字节，所有哈希相同的图片共享 |

新增表情包只写一条新元数据键，首次上传该哈希时再写一个 blob 键；更新仅重写
该条元数据；删除会移除元数据，并在没有其它引用时删除 blob。热路径工作量与
改动量成正比，不会每次重写整份索引。

## 管理 Page 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/stats` | GET | 数量、字节数与各 mime 统计 |
| `/list` | GET | 分页画廊（`limit`、`offset`） |
| `/item` | GET | 单个表情包元数据与稳定地址（`name`） |
| `/image` | GET | 页面预览用的 base64（`name`） |
| `/add` | POST | 从 `url` 或 `data_url` 存储（必填 `name`） |
| `/delete` | POST | 删除单个表情包（`name`） |
| `/clear` | DELETE | 清空当前安装下的全部表情包 |

## Tool

| Tool | 参数 | 返回 |
|------|------|------|
| `stickerhub_add_sticker` | `name`，可选 `url` 或 `data_url` | JSON `{"ok": true, "sticker": {...}}` |
| `stickerhub_get_sticker_url` | `name` | 稳定地址字符串 |
| `stickerhub_list_stickers` | 可选 `limit` | JSON `{"ok": true, "total", "items": [{name, uri, mime, size}]}` |
| `stickerhub_delete_sticker` | `name` | JSON `{"ok": bool}` |

`stickerhub_get_sticker_url` 成功时返回裸 URL 字符串；表情包不存在或调用非法时
返回以 `error:` 开头的字符串。

## 与 HumanTakeover 联动

插件的稳定接口以 Tool 形式暴露。在 HumanTakeover 的执行上下文中：

```python
url = await self.plugin.call_tool(
    "stickerhub_get_sticker_url",
    {"name": sticker_name},
    session,
    query_id,
)
if url and not url.startswith("error:"):
    components.append(platform_message.Image(url=url))
```

`call_tool` 需要 HumanTakeover 的安装授予 `plugin_tools` 能力。HumanTakeover
也可以在回复前调用
`self.plugin.call_tool("stickerhub_add_sticker", {"name", "data_url"})`
先登记表情包。

当两个插件在同一个 worker 中运行时，可直接使用 Python API：

| 方法 | 用途 |
|------|------|
| `await add_sticker(name, data, mime, source=...)` | 存储字节并返回元数据 / 地址 |
| `await add_sticker_from_url(name, url)` | 限流远端下载并存储 |
| `await add_sticker_from_base64(name, data_url)` | 存储 `data:` URL / base64 |
| `await get_sticker(name)` / `await media_url(name)` | 元数据 / 稳定地址 |
| `await list_stickers(limit, offset)` | 分页 |
| `await delete_sticker(name)` / `await clear_stickers()` | 删除 / 清空 |
| `await sticker_image(name)` | base64 预览（无公开主机时使用） |

## 测试

```bash
cd plugins/misc/StickerHub
python -m pytest tests -q
```

测试套件驱动真实的插件对象，配合记录 plugin storage 动作的桩 Host，覆盖内容
寻址、去重、大小上限、淘汰、分页、安装隔离、URL 稳定性、Page 接口与 Tool 契约。

# feishu_process_bitable_plugin

把工艺消息（文本 + 图片OCR）解析成结构化字段并写入飞书多维表格。

这个插件是 `EventListener` 方式：收到消息自动处理，不依赖模型工具调用。

## 内置工艺解析

- `particle_size`：图片/OCR 粒度数据（`D10/D50/D90/D99`）
  - 批次编码示例：`S006-FS-DB2602-117`、`S18-FS-DB2602-117`
  - 工序代码：`FS`(粉碎) / `CM`(粗磨) / `XM`(细磨) / `HP`(合批) / `SC`(烧结) / `QQT`(喷雾)
  - 默认按工序归并路由：
    - `FS` -> `crushing.A` / `crushing.B`
    - `CM/XM/HP` -> `wet_process.A` / `wet_process.B`
    - `SC` -> `sintering.A` / `sintering.B`
    - `QQT` -> `spray.A` / `spray.B`
  - 在 `wet_process` 汇总表内，`CM/XM/HP` 会写入工序前缀列，避免同批次互相覆盖：
    - 例如 `粗磨D10/粗磨D50/粗磨D90/粗磨D99`、`细磨D10...`、`合批D10...`
    - 细磨 `XM` 支持段位映射：`A/B -> 1线`、`C/D -> 2线`，并按 `细磨A/细磨B/细磨C/细磨D` 分列记录
    - 时间列为 `粗磨研磨时间(min)` / `细磨研磨时间(min)` / `合批研磨时间(min)`
    - `CM/XM/HP` 的批次号会统一归一为 `Sxxx-DA/DBxxxx-xxx`，用于三工序同批次汇总到一行
- `spray`：喷雾（A/B线，批次 + 开度/进出口温度/雾化轮转速/水分）
- `feeding`：投料（A/B线，批次 + 磷酸铁需补/碳酸锂需补/D5总量/BL总量）
- `sintering`：烧结（A/B线，批次 + 样品值 + 自动均值）
- `crushing`：粉碎压实（A/B线，批次 + 样品值 + 频率）
- `pure_water`：纯水（PH + 批次）

## 核心配置

- `app_id` / `app_secret`
- `bitable_app_token`
- `bitable_default_table_id`
- `table_routing_json`：把不同路由写入不同表
- `auto_create_table_by_route`：未配置 `table_id` 时按路由自动建表
- `table_name_routing_json`：路由 -> 表名（用于自动建表）
- `auto_create_fields`：缺列自动创建
- `enable_ocr_for_images`
- `process_switch_json`
- `merge_particle_size_to_stage_tables`：粒度数据归并到工序汇总表（默认 `true`）
- `upsert_by_batch`：按批次优先更新已有行（默认 `true`，避免同批次拆成多行）
- `upsert_match_include_route` / `upsert_match_include_line`：upsert匹配是否包含路由与产线
- `prevent_default_on_match`：命中规则即拦截默认流程（建议保持 `true`）
- `private_notify_user_id`：群消息处理结果私聊通知对象（填你的 `ou_xxx`）
- `reply_in_group`：是否允许在群聊直接回消息（工作群建议 `false`）
- `reply_in_person`：是否允许在私聊直接回复（建议 `true`）
- `private_notify_on_write` / `private_notify_on_error`：群消息成功/失败时是否私聊通知

## table_routing_json 示例

```json
{
  "spray.A": "tblAxxxx",
  "spray.B": "tblByyyy",
  "feeding.A": "tblAxxxx",
  "feeding.B": "tblByyyy",
  "sintering.A": "tblAxxxx",
  "sintering.B": "tblByyyy",
  "crushing.A": "tblAxxxx",
  "crushing.B": "tblByyyy",
  "wet_process.A": "tblWetAxxxx",
  "wet_process.B": "tblWetByyyy",
  "pure_water": "tblWater"
}
```

说明：
- 先匹配完整路由键（如 `spray.A`）
- 未命中时匹配前缀键（如 `spray`）
- 若未配置到 `table_id`，可按 `table_name_routing_json` / 默认表名自动建表
- 自动建表仍失败时，最后回退到 `bitable_default_table_id`

## 自动建表与自动补列

- 默认开启 `auto_create_table_by_route=true`、`auto_create_fields=true`
- 当 `table_routing_json` 没有命中时，插件会按路由自动找表/建表
- 默认表名（可被 `table_name_routing_json` 覆盖）：
  - `spray.A` -> `A线喷雾汇总`
  - `spray.B` -> `B线喷雾汇总`
  - `feeding.A` -> `A线投料汇总`
  - `feeding.B` -> `B线投料汇总`
  - `sintering.A` -> `A线烧结汇总`
  - `sintering.B` -> `B线烧结汇总`
  - `crushing.A` -> `A线粉碎压实汇总`
  - `crushing.B` -> `B线粉碎压实汇总`
  - `wet_process.A` -> `A线湿法汇总`
  - `wet_process.B` -> `B线湿法汇总`
  - `pure_water` -> `车间纯水PH汇总`
- 若 `merge_particle_size_to_stage_tables=false`，仍可使用 `particle_size.FS/CM/XM/HP/SC/QQT` 独立路由
- 写入前会检查字段，缺失字段自动创建（默认文本列）

`table_name_routing_json` 示例：

```json
{
  "spray.A": "A线喷雾汇总",
  "spray.B": "B线喷雾汇总",
  "feeding.A": "A线分散罐汇总",
  "feeding.B": "B线分散罐汇总",
  "sintering.A": "A线烧结压实汇总",
  "sintering.B": "B线烧结压实汇总",
  "crushing.A": "A线粉碎压实汇总",
  "crushing.B": "B线粉碎压实汇总",
  "wet_process.A": "A线湿法汇总",
  "wet_process.B": "B线湿法汇总",
  "pure_water": "车间纯水PH汇总"
}
```

## 事件行为

- 默认命中规则后阻断 LangBot 主流程（`prevent_default_on_match=true`）
- 写入成功后是否额外阻断由 `prevent_default_on_write` 控制（默认 `false`）
- 默认按批次 upsert（`upsert_by_batch=true`），同批次压实/粒度会优先合并到同一行
- 默认不回复（`reply_on_write=false`）
- 失败时默认也不回复（`reply_on_error=false`）
- 默认不在群回复（`reply_in_group=false`），允许私聊回复（`reply_in_person=true`）
- 群消息默认会私聊通知（`private_notify_on_write=true` / `private_notify_on_error=true`），通知对象由 `private_notify_user_id` 指定

推荐配置（工作群静默 + 私聊通知你）：

```json
{
  "prevent_default_on_match": true,
  "reply_in_group": false,
  "reply_in_person": true,
  "private_notify_on_write": true,
  "private_notify_on_error": true,
  "private_notify_user_id": "ou_xxx",
  "reply_text_template": "已写入飞书表格，共{count}条。\\n{details}"
}
```

## 打包

```bash
cd plugins/feishu_process_bitable_plugin
lbp build -o dist
```


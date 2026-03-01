# feishu_process_bitable_plugin

把工艺消息（文本 + 图片OCR）解析成结构化字段并写入飞书多维表格。

这个插件是 `EventListener` 方式：收到消息自动处理，不依赖模型工具调用。

## 内置工艺解析

- `particle_size`：图片/OCR 粒度数据（`D10/D50/D90/D99`）
  - 批次编码示例：`S006-FS-DB2602-117`、`S18-FS-DB2602-117`
  - 工序代码：`FS`(粉碎) / `CM`(粗磨) / `XM`(细磨) / `HP`(合批) / `QQT`(喷雾)
  - 按工序自动路由：`particle_size.FS` / `particle_size.CM` / `particle_size.XM` / `particle_size.HP` / `particle_size.QQT`
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

## table_routing_json 示例

```json
{
  "particle_size.FS": "tblFsxxxx",
  "particle_size.CM": "tblCmxxxx",
  "particle_size.XM": "tblXmxxxx",
  "particle_size.HP": "tblHpxxxx",
  "particle_size.QQT": "tblQqtxxxx",
  "spray.A": "tblAxxxx",
  "spray.B": "tblByyyy",
  "feeding.A": "tblAxxxx",
  "feeding.B": "tblByyyy",
  "sintering.A": "tblAxxxx",
  "sintering.B": "tblByyyy",
  "crushing.A": "tblAxxxx",
  "crushing.B": "tblByyyy",
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
  - `particle_size.FS` -> `粉碎工序粒度汇总`
  - `particle_size.CM` -> `粗磨工序粒度汇总`
  - `particle_size.XM` -> `细磨工序粒度汇总`
  - `particle_size.HP` -> `合批工序粒度汇总`
  - `particle_size.QQT` -> `喷雾工序粒度汇总`
  - `spray.A` -> `A线喷雾汇总`
  - `spray.B` -> `B线喷雾汇总`
  - `feeding.A` -> `A线投料汇总`
  - `feeding.B` -> `B线投料汇总`
  - `sintering.A` -> `A线烧结汇总`
  - `sintering.B` -> `B线烧结汇总`
  - `crushing.A` -> `A线粉碎压实汇总`
  - `crushing.B` -> `B线粉碎压实汇总`
  - `pure_water` -> `车间纯水PH汇总`
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
  "pure_water": "车间纯水PH汇总"
}
```

## 事件行为

- 默认不阻断 LangBot 主流程（`prevent_default_on_write=false`）
- 默认不回复（`reply_on_write=false`）
- 失败时默认也不回复（`reply_on_error=false`）

## 打包

```bash
cd plugins/feishu_process_bitable_plugin
lbp build -o dist
```


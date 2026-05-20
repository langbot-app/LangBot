# feishu_process_bitable_plugin

把工艺消息（文本 + 图片OCR）解析成结构化字段并写入飞书多维表格。

这个插件是 `EventListener` 方式：收到消息自动处理，不依赖模型工具调用。

## 内置工艺解析

- `particle_size`：图片/OCR 粒度数据（`D10/D50/D90/D99`）
  - 批次编码示例：`S006-FS-DB2602-117`、`S18-FS-DB2602-117`
  - 工序代码：`FS`(粉碎) / `CM`(粗磨) / `XM`(细磨) / `HP`(合批) / `SC`(烧结) / `QQT`(喷雾)
  - 默认按工序归并路由：
    - `FS` -> `crushing.{产线}`，产线支持 `A/B/C/D/E`
    - `CM/XM/HP` -> `wet_process.{产线}`，产线支持 `A/B/C/D/E`
    - `SC` -> `sintering.{产线}`，产线支持 `A/B/C/D/E`
    - `QQT` -> `spray.{产线}`，产线支持 `A/B/C/D/E`
  - 在 `wet_process` 汇总表内，`CM/XM/HP` 会写入工序前缀列，避免同批次互相覆盖：
    - 例如 `粗磨D10/粗磨D50/粗磨D90/粗磨D99`、`细磨D10...`、`合批D10...`
    - 细磨 `XM` 支持段位映射：`A/B -> 1线`、`C/D -> 2线`，并按 `细磨1线/细磨2线` 两套字段记录
    - 细磨 `XM` 额外支持固含量格式：`S006-XM-DB2602-130-B-160min：40.89%DC`，写入 `细磨1线固含量(%)` 或 `细磨2线固含量(%)`
    - 时间列为 `粗磨研磨时间(min)` / `细磨研磨时间(min)` / `合批研磨时间(min)`
    - `CM/XM/HP` 的批次号会统一归一为 `Sxxx-D{产线}xxxx-xxx`，用于三工序同批次汇总到一行
- `crushing` 扩展支持 `A1/A2/B1/B2/C1/C2/D1/D2/E1/E2`：
  - 粉碎粒度中 `*1 -> 粉碎1线*`，`*2 -> 粉碎2线*`（如 `A1/C1/E1 -> 粉碎1线D10`，`B2/D2 -> 粉碎2线D50`）
  - 压实格式 `S006-FS-DB2602-125-B1-120min-53HZ：2.491` 会写入 `粉碎1线压实值/粉碎时间（min）/频率(HZ)`
  - 参数块格式 `A2粉碎:S18-DA2603-005 ...` 支持提取分级电机、喂料频率、研磨压力、密封气压、收尘差压、过滤器压、露点
- `spray`：喷雾（A/B/C/D/E线，批次 + 开度/进出口温度/雾化轮转速/水分）
  - 额外支持快速水分格式：`S006-QQT-DB2602-130-B-60min：1.08％MC`（自动写入 `水分`，并归并到 `S006-DB2602-130`）
- `feeding`：投料（A/B/C/D/E线，批次 + 磷酸铁需补/碳酸锂需补/D5总量/BL总量）
- `product`：成品数据（按系列分表，成品批次 + 产线 + 段位 + 送检项目/送检状态/关注项/下料说明）
  - 批次编码示例：`S18-CP-DA2605-104-A1`、`S20-CP-DA2605-101-A1`
  - 兼容旧写法：`S18--DA2605-085-Cs-A1` 会归一为成品批次并记录后缀
  - 状态文本示例：`全检已送检`、`水分，扣电已送`、`铜锌颗粒，大颗粒`、`三倍全检已送检`
  - 图片消息会先走飞书 OCR，再按同一套成品规则解析
  - OCR 指标会写入可统计字段：`成品压实`、`0.1C充电`、`0.1C放电`、`首效`、`平台效率`、`残碱(Li+)`、`碳含量`、`粉阻(粉末电阻)`、`比表(麦克比表)`、`pH`
  - 扣电截图会按批次解析 `0.1C` / `1C` 两套指标：首充均值、首放均值、首效均值、恒流比均值、3.2V平台比容量均值、平台占比均值
  - 兼容表格截图里的无段位样品批号，例如 `S18-DA2605-085-CS`，并记录 `样品批号`、`检测日期`
- `sintering`：烧结（A/B/C/D/E线，批次 + 样品值 + 自动均值）
- `crushing`：粉碎压实（A/B/C/D/E线，批次 + 样品值 + 频率）
- `pure_water`：纯水（PH + 批次）
- 产线批次主编码支持 `A/B/C/D/E`，例如 `S20-DA2604-001`、`S20-DC2604-001`、`S20-DE2604-001`
- `kiln_batch_io`：窑炉批次进窑/出窑（批次 + 窑炉段 + 窑位 + 进/出窑开始结束时间）
  - 头行示例：`DA2603-021批次结束出窑`、`DA2603-027批次开始进窑`
  - 明细示例：`A2-1--06：23`、`B1--2---01:21`
  - 窑炉段采用“白名单优先 + 兼容扩展”：优先识别 `A1/A2/B1/B2/C1/C2/D1/D2/E1/E2`，并兼容如 `F1` 等扩展段位
  - 行模式默认 `segment`：同一批次+窑段仅一行，时间列按窑位展开（如 `1号进窑开始时间`、`2号出窑结束时间`）
  - 可切换 `slot`：按 `批次+窑段+窑位` 分行写入（旧行为）

## 核心配置

- `app_id` / `app_secret`
- `bitable_app_token`
- `bitable_default_table_id`
- `table_routing_json`：把不同路由写入不同表
- `auto_create_table_by_route`：未配置 `table_id` 时按路由自动建表（生产默认 `false`）
- `table_name_routing_json`：路由 -> 表名（用于自动建表）
- `auto_create_fields`：缺列自动创建（生产默认 `false`）
- `enable_ocr_for_images`
- `process_switch_json`（默认包含 `product=true`）
- `kiln_batch_io_row_mode`：`segment|slot`（默认 `segment`）
- `merge_particle_size_to_stage_tables`：粒度数据归并到工序汇总表（默认 `true`）
- `upsert_by_batch`：按批次优先更新已有行（默认 `true`，避免同批次拆成多行）
- `upsert_match_include_route` / `upsert_match_include_line`：upsert匹配是否包含路由与产线
- `prevent_default_on_match`：命中规则即拦截默认流程（建议保持 `true`）
- `private_notify_user_id`：群消息处理结果私聊通知对象（填你的 `ou_xxx`）
- `reply_in_group`：是否允许在群聊直接回消息（工作群建议 `false`）
- `reply_in_person`：是否允许在私聊直接回复（建议 `true`）
- `private_notify_on_write` / `private_notify_on_error`：群消息成功/失败时是否私聊通知
- `time_zone`：时间显示时区（默认 `Asia/Shanghai`）
- `time_format`：时间显示格式（默认 `%Y-%m-%d %H:%M:%S`）
- `enable_recall_restore_previous`：撤回时优先恢复上一版本（默认 `true`）
- `history_table_id` / `history_table_name`：写入历史快照表，用于撤回恢复
- `auto_create_history_table`：未指定历史表 ID 时自动创建历史表（默认 `true`）

## table_routing_json 示例

```json
{
  "spray.A": "tblAxxxx",
  "spray.C": "tblCxxxx",
  "spray.E": "tblExxxx",
  "spray.B": "tblByyyy",
  "product.S18": "tblProductS18xxxx",
  "product.S20": "tblProductS20yyyy",
  "product.S006": "tblProductS006xxxx",
  "feeding.A": "tblAxxxx",
  "feeding.C": "tblCxxxx",
  "feeding.E": "tblExxxx",
  "feeding.B": "tblByyyy",
  "sintering.A": "tblAxxxx",
  "sintering.C": "tblCxxxx",
  "sintering.E": "tblExxxx",
  "sintering.B": "tblByyyy",
  "crushing.A": "tblAxxxx",
  "crushing.C": "tblCxxxx",
  "crushing.E": "tblExxxx",
  "crushing.B": "tblByyyy",
  "wet_process.A": "tblWetAxxxx",
  "wet_process.C": "tblWetCxxxx",
  "wet_process.E": "tblWetExxxx",
  "wet_process.B": "tblWetByyyy",
  "pure_water": "tblWater",
  "kiln_batch_io": "tblKilnxxxx"
}
```

说明：
- 先匹配完整路由键（如 `spray.A`）
- 未命中时匹配前缀键（如 `spray`）
- 若开启 `auto_create_table_by_route` 且未配置到 `table_id`，可按 `table_name_routing_json` / 默认表名自动建表
- 自动建表仍失败时，最后回退到 `bitable_default_table_id`

## 自动建表与自动补列

- 生产默认关闭 `auto_create_table_by_route=false`、`auto_create_fields=false`
- 当 `table_routing_json` 没有命中且 `auto_create_table_by_route=false` 时，插件不会自动建表，会返回配置错误
- 默认表名（可被 `table_name_routing_json` 覆盖）：
  - `spray.A` -> `A线喷雾汇总`
  - `spray.B` -> `B线喷雾汇总`
  - `spray.C` -> `C线喷雾汇总`
  - `spray.D` -> `D线喷雾汇总`
  - `spray.E` -> `E线喷雾汇总`
  - `feeding.A` -> `A线投料汇总`
  - `feeding.B` -> `B线投料汇总`
  - `feeding.C` -> `C线投料汇总`
  - `feeding.D` -> `D线投料汇总`
  - `feeding.E` -> `E线投料汇总`
  - `product.S006` -> `S006成品数据汇总`
  - `product.S18` -> `S18成品数据汇总`
  - `product.S20` -> `S20成品数据汇总`
  - 其他成品系列默认 -> `<系列>成品数据汇总`
  - `sintering.A` -> `A线烧结汇总`
  - `sintering.B` -> `B线烧结汇总`
  - `sintering.C` -> `C线烧结汇总`
  - `sintering.D` -> `D线烧结汇总`
  - `sintering.E` -> `E线烧结汇总`
  - `crushing.A` -> `A线粉碎压实汇总`
  - `crushing.B` -> `B线粉碎压实汇总`
  - `crushing.C` -> `C线粉碎压实汇总`
  - `crushing.D` -> `D线粉碎压实汇总`
  - `crushing.E` -> `E线粉碎压实汇总`
  - `wet_process.A` -> `A线湿法汇总`
  - `wet_process.B` -> `B线湿法汇总`
  - `wet_process.C` -> `C线湿法汇总`
  - `wet_process.D` -> `D线湿法汇总`
  - `wet_process.E` -> `E线湿法汇总`
  - `pure_water` -> `车间纯水PH汇总`
  - `kiln_batch_io` -> `窑炉批次进窑出窑表`
  - `kiln_batch_io.phase2` -> `二期窑炉批次进窑出窑表`
- 若 `merge_particle_size_to_stage_tables=false`，仍可使用 `particle_size.FS/CM/XM/HP/SC/QQT` 独立路由
- 写入前会检查字段；默认缺字段时报错，只有显式开启 `auto_create_fields=true` 时才会自动创建（默认文本列）

`table_name_routing_json` 示例：

```json
{
  "spray.A": "A线喷雾汇总",
  "spray.B": "B线喷雾汇总",
  "spray.C": "C线喷雾汇总",
  "spray.D": "D线喷雾汇总",
  "spray.E": "E线喷雾汇总",
  "product.S006": "S006成品数据汇总",
  "product.S18": "S18成品数据汇总",
  "product.S20": "S20成品数据汇总",
  "feeding.A": "A线分散罐汇总",
  "feeding.B": "B线分散罐汇总",
  "feeding.C": "C线分散罐汇总",
  "feeding.D": "D线分散罐汇总",
  "feeding.E": "E线分散罐汇总",
  "sintering.A": "A线烧结压实汇总",
  "sintering.B": "B线烧结压实汇总",
  "sintering.C": "C线烧结压实汇总",
  "sintering.D": "D线烧结压实汇总",
  "sintering.E": "E线烧结压实汇总",
  "crushing.A": "A线粉碎压实汇总",
  "crushing.B": "B线粉碎压实汇总",
  "crushing.C": "C线粉碎压实汇总",
  "crushing.D": "D线粉碎压实汇总",
  "crushing.E": "E线粉碎压实汇总",
  "wet_process.A": "A线湿法汇总",
  "wet_process.B": "B线湿法汇总",
  "wet_process.C": "C线湿法汇总",
  "wet_process.D": "D线湿法汇总",
  "wet_process.E": "E线湿法汇总",
  "pure_water": "车间纯水PH汇总",
  "kiln_batch_io": "窑炉批次进窑出窑表"
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

## 撤回回滚（方案B）

- 平台接入飞书撤回事件后，插件可按 `source_message_id_field`（默认 `源消息ID`）定位并回滚。  
- 默认会为每次写入保存历史快照；当后续消息覆盖了同一行时，撤回新消息会优先恢复上一版本。  
- 若找不到上一版本快照（例如该消息是首次创建该行），则回退为“标记撤回”（默认更新字段）：`是否撤回=是`、`撤回时间`、`撤回类型`。  
- 关键配置：
  - `enable_recall_revert`：是否启用撤回回滚（默认 `true`）
  - `enable_recall_restore_previous`：是否启用“恢复上一版本”逻辑（默认 `true`）
  - `history_table_id` / `history_table_name`：历史快照表配置
  - `auto_create_history_table`：历史表不存在时是否自动创建（默认 `true`）
  - `prevent_default_on_recall`：撤回事件是否阻断默认流程（默认 `true`）
  - `recall_scan_all_tables`：找不到路由缓存时是否扫描全部表（默认 `true`）
  - `reply_on_recall`：撤回处理完成后是否反馈（默认 `false`）

## 打包

```bash
cd plugins/feishu_process_bitable_plugin
lbp build -o dist
```


# feishu_process_bitable_plugin

把工艺消息（文本 + 图片OCR）解析成结构化字段并写入飞书多维表格。

这个插件是 `EventListener` 方式：收到消息自动处理，不依赖模型工具调用。

## 内置工艺解析

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
- `enable_ocr_for_images`
- `process_switch_json`

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
  "pure_water": "tblWater"
}
```

说明：
- 先匹配完整路由键（如 `spray.A`）
- 未命中时匹配前缀键（如 `spray`）
- 仍未命中则使用 `bitable_default_table_id`

## 事件行为

- 默认不阻断 LangBot 主流程（`prevent_default_on_write=false`）
- 默认不回复（`reply_on_write=false`）
- 失败时默认也不回复（`reply_on_error=false`）

## 打包

```bash
cd plugins/feishu_process_bitable_plugin
lbp build -o dist
```


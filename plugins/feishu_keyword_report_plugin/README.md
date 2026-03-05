# feishu_keyword_report_plugin

通过口令查询飞书**在线表格（Sheets）**生成日报；在线表格失败时可自动回退到飞书**多维表（Bitable）**简报。

默认口令：`日报`

## 功能说明

- 监听群聊/私聊文本消息
- 支持口令参数：日期、线别
- 在线表格优先生成标准日报（复用 `day` 项目指标提取与文本结构）
- `data_source_mode=auto` 时，在线表格失败自动回退多维表简报

## 数据源模式

- `auto`：在线表格优先，失败回退多维表
- `sheets`：仅在线表格
- `bitable`：仅多维表（简版）

## 口令协议

格式：`日报 [YYYY-MM-DD] [线别列表]`

示例：

- `日报`
- `日报 2026-03-03`
- `日报 S18-A线,S006-B线`
- `日报 2026-03-03 S18-A线,S006-B线`

## 日报口令使用教程

### 1. 先完成配置

- 在插件配置中填写：`app_id`、`app_secret`、`sheets_spreadsheet_token`
- 建议设置：`data_source_mode=auto`（在线表格失败时自动回退多维表）
- 确认：`keyword_commands` 包含 `日报`

### 2. 常用口令

- 查询最新日报：`日报`
- 查询指定日期：`日报 2026-03-03`
- 查询指定线别：`日报 S18-A线,S006-B线`
- 查询指定日期+线别：`日报 2026-03-03 S18-A线,S006-B线`

### 3. 参数规则

- 日期格式必须是：`YYYY-MM-DD`
- 线别可用逗号分隔：`,` 或 `，`
- 线别名称必须与在线表格工作表标题一致
- 不写线别时，默认按 `sheets_sheet_names`（为空则尝试全部工作表）

### 4. 常见报错排查

- `指定线别不存在`：输入线别与在线表格工作表名不一致
- `日报查询失败：未配置 sheets_spreadsheet_token`：未配置在线表格 token
- `日报查询失败：在线表格失败...`：检查应用权限、表格共享范围、token 是否正确
- 回复中出现 `以下线别未纳入日报`：表示部分线别读取失败，已对其余线别正常生成日报

## 关键配置

### 通用

- `app_id` / `app_secret`
- `token_endpoint`
- `timeout_seconds`
- `keyword_commands`（默认 `日报`）
- `reply_in_group` / `reply_in_person`

### 在线表格日报

- `data_source_mode`：`auto|sheets|bitable`（默认 `auto`）
- `sheets_spreadsheet_token`
- `sheets_sheet_names`：默认线别工作表（逗号分隔）
- `sheets_range`：默认 `A1:ZZ2000`
- `date_mode`：`global|per-line`（默认 `global`）
- `report_show_placeholder_sections`：是否显示“原料bom/配方/下一步/工艺验证”占位段（默认 `false`）
- `lookback_days` / `trend_days`
- `stale_threshold_process` / `stale_threshold_product` / `stale_threshold_electrochem`
- `spec_registry_json`：可选 JSON 字符串，未配置时使用内置规格

### 多维表回退（兼容旧链路）

- `bitable_app_token`
- `sintering_table_ids`
- `sintering_table_names`
- `route_field` / `batch_field` / `message_time_field`
- `detail_max_fields`
- `scan_limit`
- `no_data_text`

## 示例回复（在线表格日报）

```text
2026.03.03数据表更新（S18-A线、S006-B线）：
3、制程：烧结压实 S18-A线 2.36（正常...）；S006-B线 2.49（正常...）。粉碎压实 ...
4、成品：
  ①成品压实：...
  ②0.1C充电：...
  ...
```

## 示例回复（自动回退多维表）

```text
【在线表格查询失败，已回退多维表】...失败原因...
当前出窑批次及烧结压实（多维表回退）：
A线：...
B线：...
```

## 打包

```bash
cd plugins/feishu_keyword_report_plugin
lbp build -o dist
```

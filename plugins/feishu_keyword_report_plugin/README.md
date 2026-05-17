# feishu_keyword_report_plugin

通过口令查询飞书数据，支持两条链路：

- `日报`：优先读 Feishu Sheets 生成标准日报，失败可回退 Feishu Bitable 简报。
- `摸料`：联动窑炉批次表 + 烧结表 + Sheets 配方表，返回指定段位当前出窑批次与压实信息。

默认情况下，`日报` 与 `摸料` 的配方表检索都会自动纳入符合 `S18-*线` / `S006-*线` / `S20-*线` 规则的工作表；后续新增 `S006-A线`、`S18-C线`、`S20-C线` 等无需改代码。

## 口令协议

### 1. 日报（兼容原行为）

格式：`日报 [YYYY-MM-DD] [线别列表]`

示例：

- `日报`
- `日报 2026-03-03`
- `日报 S18-A线,S006-B线`
- `日报 2026-03-03 S18-A线,S006-B线`

### 2. 摸料（新增）

格式：`摸料 A1|A2|B1|B2|C1|C2`

示例：

- `摸料 A1`
- `摸料 A2`
- `摸料 B1`
- `摸料 B2`
- `摸料 C1`
- `摸料 C2`

规则：

- 仅支持单段位。
- 当前默认开放 `A1|A2|B1|B2|C1|C2`；可通过 `touch_material_segments` 继续扩展或收窄。
- 大小写不敏感（如 `摸料 a2`）。
- 可去标点（如 `摸料，A2`）。
- 参数无效时回复会按当前配置段位生成，例如：`摸料参数无效，请使用：摸料 A1|A2|B1|B2|C1|C2。`

## 摸料链路说明

### 当前出窑批次来源

- 数据表：`kiln_batch_io` 对应表（默认表名 `窑炉批次进窑出窑表,二期窑炉批次进窑出窑表`）。
- 判定策略：同段位内“出窑开始时间优先，缺失回退出窑结束时间”，取时间最大批次。
- 兼容两种行模式：
  - `segment`：`1号出窑开始时间/2号...`
  - `slot`：`窑位 + 出窑开始时间`

### 压实来源

- 数据表：烧结表（`sintering_table_ids/names`）。
- 匹配策略：按批次归一（如 `S18-SC-DA2603-005` 与 `DA2603-005`）+ 段位（如 `A2`）。
- 输出：统一整理为短格式（如 `A2-1：2.345`），避免回复原始长字段名。
- 若无压实：输出 `烧结压实未出`。

### 配方六项与窑温来源

- 来源：日报使用的同一 Sheets 数据源（`sheets_spreadsheet_token`）。
- 字段：`铁磷比、锂量、酸量、钛量、糖量、peg量、窑炉温度`。
- 字段缺失统一显示 `--`。
- Sheet 优先级：
  - A1/A2 优先 A 线 Sheet
  - B1/B2 优先 B 线 Sheet
  - C1/C2 优先 C 线 Sheet
  - 未命中回退全量 Sheet 扫描

### 物理性质推断

- 输入：压实均值。
- 三档默认文案（可配置）：
  - `low`
  - `medium`
  - `high`
- 无压实时不输出推断文案。

### 摸料回复格式

主行：

```text
{批次}（{铁磷比}+{锂量}+{酸量}+{钛量}+{糖量}+{peg量}）{段位}-{槽位列表}-{窑炉温度}{物料性质文案}
```

第二段与明细：

- 有压实：

```text
烧结压实
{样本1}
{样本2}
{样本3}
```

- 无压实：

```text
烧结压实未出
```

## 关键配置

### 通用配置

- `app_id` / `app_secret`
- `token_endpoint`
- `timeout_seconds`
- `reply_in_group` / `reply_in_person`

### 日报配置

- `keyword_commands`（默认 `日报`）
- `data_source_mode`：`auto|sheets|bitable`
- `sheets_spreadsheet_token`
- `sheets_sheet_names`：可选补充工作表列表；未配置也会自动扫描并纳入 `S18-*线` / `S006-*线` / `S20-*线`
- `sheet_auto_discovery_patterns_json`：日报工作表自动发现正则数组，例如 `["(S18|S006|S20)-.+线"]`
- `sheets_range`
- `sheet_snapshot_header_rows`（截图固定保留前几行，默认 `3`）
- `sheet_snapshot_tail_nonempty_rows`（截图保留尾部有效行数，默认 `20`）
- `date_mode`
- `report_show_placeholder_sections`
- `lookback_days` / `trend_days`
- `report_show_process_trend`
- `report_show_product_trend`
- `stale_threshold_process` / `stale_threshold_product` / `stale_threshold_electrochem`
- `spec_registry_json`
- `spec_limits_json`：追加规格上下限规则，格式同 `spec_registry_json`
- `report_metric_aliases_json`：日报指标列别名，可按 `default`、`products`、`lines` 配置

### 摸料配置（新增）

- `touch_material_commands`（默认 `摸料`）
- `touch_material_segments`（默认 `A1,A2,B1,B2,C1,C2`）
- `kiln_batch_table_ids`
- `kiln_batch_table_names`（默认 `窑炉批次进窑出窑表,二期窑炉批次进窑出窑表`）
- 配方表检索默认复用日报的自动选表逻辑，会自动纳入新增的 `S18-*线` / `S006-*线` / `S20-*线`
- `touch_recipe_field_aliases_json`
- `touch_material_infer_rules_json`
- `touch_material_no_data_text`（默认 `未查到当前出窑批次或烧结压实数据。`）
- 找不到当前出窑批次、烧结压实或配方数据时，回复会追加缺失环节提示。

### Bitable 配置（日报回退与摸料共用）

- `bitable_app_token`
- `sintering_table_ids`
- `sintering_table_names`
- `route_field`
- `batch_field`
- `message_time_field`
- `scan_limit`
- `detail_max_fields`
- `no_data_text`（日报回退用）

## 打包

```bash
cd plugins/feishu_keyword_report_plugin
lbp build -o dist
```

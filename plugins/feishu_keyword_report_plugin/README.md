# feishu_keyword_report_plugin

通过口令查询飞书多维表，回复“当前出窑批次 + 烧结压实”。

默认口令：`摸料`

## 功能说明

- 监听群聊/私聊文本消息
- 命中口令后查询烧结数据表
- 返回 A 线、B 线最新批次及压实明细（优先展示 `*均值` 字段）

## 关键配置

- `app_id` / `app_secret`
- `bitable_app_token`
- `keyword_commands`：触发口令，逗号分隔（默认 `摸料`）
- `sintering_table_ids`：烧结表 `table_id` 列表（推荐直接配置）
- `sintering_table_names`：未配 `table_id` 时按表名查找（默认 `A线烧结汇总,B线烧结汇总`）
- `route_field` / `batch_field` / `message_time_field`
- `detail_max_fields`：每条回复展示的明细字段数
- `scan_limit`：查询记录上限
- `reply_in_group` / `reply_in_person`

## 示例回复

```text
当前出窑批次及烧结压实：
A线：S18-SC-DA2603-005 | A1-均值=2.364, A2-均值=2.358 | 时间 2026-03-03T10:55:14+08:00
B线：S006-SC-DB2602-130 | B1-均值=2.491 | 时间 2026-03-03T10:48:22+08:00
```

## 打包

```bash
cd plugins/feishu_keyword_report_plugin
lbp build -o dist
```


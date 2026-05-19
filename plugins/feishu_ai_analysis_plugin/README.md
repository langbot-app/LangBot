# feishu_ai_analysis_plugin

基于飞书“制程”多维表和“2026制程及成品数据”电子表格，提供 LFP 批次分析、制程异常原因分析、成品数据分析、配方复盘和相似批次复盘入口。

插件定位是“AI 辅助分析”，不是自动决策系统。AI 只基于插件整理出的证据生成报告，不直接修改飞书数据、不自动放行/报废/降级、不自动改配方。

## 能力边界

- 制程异常原因分析：读取投料、湿法、喷雾、烧结、粉碎、窑炉进出窑等 Base 表，生成批次宽表和规则诊断，再由 AI 输出原因排序和措施建议。
- 成品数据自动分析：读取成品 Sheets，做表头识别、数值汇总、缺失统计、趋势摘要和数据处理建议。
- 配方和原料优化：当前做复盘和推荐方向，不直接自动优化生产配方；需要原料批次、供应商、配方版本、成品全指标和放行结果后才能升级为实验推荐。

## 口令

```text
批次分析 S18-DA2603-005
制程复盘 DA2603-005
异常分析 S18-DA2603-005 压实偏低
成品分析 S18-A线
成品分析 2026-05-19 S18-A线
配方复盘 S18-DA2603-005
配方建议 S18-DA2603-005
相似批次 S18-DA2603-005
```

## 推荐配置

```json
{
  "process_base_token": "https://lopal603906.feishu.cn/wiki/PxcfwOM3Ci9wVokRhF3cJHT1ngf",
  "product_spreadsheet_token": "https://lopal603906.feishu.cn/wiki/KvfTwqZvGiG6hikbbKtcwkQmnvg",
  "product_sheet_patterns": "成品数据源,S18,S006,S20",
  "product_range": "A1:ZZ2000",
  "scan_limit": "500",
  "enable_ai": true,
  "llm_base_url": "https://api.161201.xyz/v1",
  "llm_model": "gpt-5",
  "llm_temperature": "0.2"
}
```

`llm_api_key` 按部署环境填写。若不配置 AI，插件会使用规则引擎和统计摘要兜底回复。

注意：`llm_base_url` 需要包含 `/v1`。例如 `https://api.161201.xyz/v1`，不要只填裸域名。

## 实机测试记录

已使用以下链路完成实机验证：

- 飞书应用凭据可获取 `tenant_access_token`
- 制程 Base 可读，识别到 23 张表
- 成品 Sheets 可读，识别到 15 个工作表
- 批次 `S18-DA2603-005` 可生成批次宽表
- `gpt-5` 可生成制程异常分析报告

测试口令示例：

```text
异常分析 S18-DA2603-005 压实偏低
```

## 默认制程表路由

为空时使用内置路由：

- `feeding`：A/B/C/D/E 线投料汇总
- `wet_process`：A/B/C/D/E 线湿法汇总
- `spray`：A/B/C/D/E 线喷雾汇总
- `sintering`：A/B/C/D/E 线烧结汇总
- `crushing`：A/B/C/D/E 线粉碎压实汇总
- `kiln`：窑炉批次进窑出窑表、二期窑炉批次进窑出窑表

如现场表名不同，可配置 `process_tables_json`：

```json
{
  "feeding": ["A线投料汇总", "B线投料汇总"],
  "wet_process": ["A线湿法汇总", "B线湿法汇总"],
  "spray": ["A线喷雾汇总", "B线喷雾汇总"],
  "sintering": ["A线烧结汇总", "B线烧结汇总"],
  "crushing": ["A线粉碎压实汇总", "B线粉碎压实汇总"],
  "kiln": ["窑炉批次进窑出窑表", "二期窑炉批次进窑出窑表"]
}
```

## AI 输入原则

插件不会把整张表发给 AI。流程是：

```text
飞书取数 -> 批次归一化 -> 批次宽表 -> 规则诊断 -> 压缩证据 JSON -> AI 报告
```

这样可以降低泄露面、减少幻觉，并保证报告有可追溯证据。

## 安全边界

- 不写入、不删除、不修改飞书原始数据。
- 不自动改配方、放行、降级或报废。
- 异常和配方建议必须标注为建议或待验证项。
- AI 调用失败时使用规则兜底，不阻塞现场查询。

## 打包

```bash
cd plugins/feishu_ai_analysis_plugin
lbp build -o dist
```

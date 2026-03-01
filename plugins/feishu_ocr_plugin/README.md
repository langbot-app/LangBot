# feishu_ocr_plugin

这个插件现在支持两种能力：

1. 工具 `feishu_ocr_image`：可被模型主动调用，做图片 OCR。  
2. 事件监听器：收到消息后自动处理（可选 OCR 图片），按规则抽取字段，并写入飞书多维表格（Bitable）。

## 目标场景

- 不依赖模型回复。
- 消息来就处理并入表。
- 是否回复、是否阻断默认流程都可配置。

## 核心配置

- `app_id` / `app_secret`：飞书应用凭证。  
- `bitable_app_token` / `bitable_table_id`：目标多维表格。  
- `rules_json`：字段抽取规则。  
- `prevent_default_on_write`：写入成功后是否阻断默认流程（默认 `true`）。  
- `reply_on_write`：写入成功后是否回复（默认 `false`）。  

## rules_json 示例

```json
{
  "kv_aliases": {
    "姓名": ["姓名", "name"],
    "电话": ["电话", "手机号", "phone"]
  },
  "regex_extractors": [
    {
      "field": "金额",
      "pattern": "金额[：: ]*(?P<value>\\d+(?:\\.\\d+)?)",
      "group": "value"
    }
  ],
  "constant_fields": {
    "来源": "LangBot"
  }
}
```

说明：

- `kv_aliases`：按 `字段名: 候选别名列表` 做键值对抽取。  
- `regex_extractors`：正则抽取，写入指定字段。  
- `constant_fields`：固定值字段，每条都写入。  

## 内置写入字段

插件默认还会写入这些字段名（可在配置中改名）：

- `Raw Text`
- `OCR Text`
- `Sender ID`
- `Launcher ID`
- `Launcher Type`
- `Message Time`

建议在飞书表格中先创建对应文本列。

## 开发与打包

在插件目录执行：

```bash
lbp run
```

构建本地包：

```bash
lbp build -o dist
```

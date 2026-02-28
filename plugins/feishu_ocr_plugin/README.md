# feishu_ocr_plugin

调用飞书 OCR 接口识别图片文字（`optical_char_recognition:image`）。

## 功能

- 提供一个工具组件：`feishu_ocr_image`
- 支持两种入参：
  - `image_url`
  - `image_base64`（支持 `data:image/...;base64,...`）

## 配置

在插件配置页填写：

- `app_id`
- `app_secret`

可选配置：

- `token_endpoint`
- `ocr_endpoint`
- `timeout_seconds`

## 用法

1. 安装插件后，在对应 Pipeline 中启用该插件。
2. 让模型调用工具 `feishu_ocr_image`，并传入 `image_url` 或 `image_base64`。
3. 返回字段：
   - `success`
   - `text`（拼接后的文本）
   - `text_list`（飞书原始识别数组）

## 开发测试

在插件目录执行：

```bash
lbp run
```

构建本地包：

```bash
lbp build -o dist
```

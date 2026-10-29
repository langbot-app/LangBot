# GeneralParsers

LangBot 官方通用文档解析器插件，将文件提取为结构化文本，供 KnowledgeEngine 插件（如 LangRAG）使用。

## 支持格式

| 格式 | MIME Type | 解析方式 |
|------|-----------|---------|
| PDF | `application/pdf` | 基于 PyMuPDF 的版面感知解析，支持表格、分页标记和可选视觉增强 |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx 提取段落/表格，并可选识别内嵌图片 |
| Markdown | `text/markdown` | 转 HTML 后结构化提取（标题、列表、代码块、表格） |
| HTML | `text/html` | BeautifulSoup 提取（自动移除 script/style） |
| TXT | `text/plain` | 自动编码检测（chardet） |
| 图片 | `image/png`、`image/jpeg`、`image/webp`、`image/gif`、`image/bmp`、`image/tiff` | 配置视觉模型后可直接识别 |

## 架构

```
┌──────────────────────────────────────────────┐
│      KnowledgeEngine 插件（如 LangRAG）        │
│      分块 → Embedding → 存储 → 检索            │
└──────────────────┬───────────────────────────┘
                   │ invoke_parser (RPC)
┌──────────────────▼───────────────────────────┐
│          GeneralParsers                      │
│                                              │
│  文件字节 → 格式识别 → 解析 → ParseResult       │
│                                              │
│  ParseResult:                                │
│    ├── text: 完整提取文本                      │
│    ├── sections: 按标题拆分的段落列表            │
│    │   └── TextSection(content, heading,      │
│    │                   level)                 │
│    └── metadata: 文件名、MIME 类型等            │
└──────────────────────────────────────────────┘
```

## 特性

- **可选视觉模型支持** - 可配置视觉大模型，对扫描版 PDF 做 OCR，并识别 PDF/DOCX 内嵌图片和直接上传的图片文件
- **增强的 PDF 解析** - 基于 PyMuPDF 保留分页边界，合并表格内容，并输出更丰富的文档元数据
- **扫描版 PDF 处理** - 自动检测疑似扫描页，配置视觉模型后会进行 OCR
- **跨格式图片识别** - 可将 PDF/DOCX 内嵌图片和直接上传图片转换为适合后续检索的文本结果
- **页眉页脚过滤** - 自动识别并过滤 PDF 中重复出现的页眉和页脚
- **段落结构识别** - 自动检测 Markdown 风格标题（`# ~ ######`），按标题拆分为带层级的 sections
- **表格转 Markdown** - PDF/HTML/Markdown 中的表格自动转换为 Markdown 表格格式
- **异步解析** - 文件解析在线程池中执行，不阻塞事件循环
- **编码自动检测** - 使用 chardet 检测文件编码，支持 GBK、UTF-8 等
- **格式回退** - 不支持的格式自动尝试作为纯文本解析

## 配置项

插件当前提供一个可选配置项：

- `vision_llm_model_uuid`：视觉模型。用于扫描页 OCR、PDF/DOCX 图片识别，以及直接上传图片的解析。

如果不配置这个选项，GeneralParsers 仍然可以正常工作，但图片内容只会保留占位信息，PDF 也只会做纯文本/版面解析，不会做视觉增强。

## 使用方式

1. 在 LangBot 中安装本插件
2. 如果需要扫描版 PDF OCR、DOCX/PDF 图片识别，或直接解析图片文件，可额外配置视觉模型
3. 上传文件到知识库时，选择 GeneralParsers 作为解析器
4. 解析结果自动传递给 KnowledgeEngine 插件进行后续处理

## 输出结构

GeneralParsers 返回结构化的 `ParseResult`，包含：

- `text`：完整提取文本
- `sections`：按标题拆分的结构化段落，适合依赖章节信息的分块策略
- `metadata`：文档元数据，例如文件名、MIME 类型、页数、是否含表格、是否检测到扫描页、是否使用视觉模型等

最近 PDF 解析会补充的 metadata 字段包括：

- `page_count`
- `word_count`
- `has_tables`
- `has_scanned_pages`
- `headers_footers_removed`
- `vision_used`
- `vision_tasks_count`
- `vision_scanned_pages_count`
- `vision_images_described_count`

## 开发

```bash
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中配置 `DEBUG_RUNTIME_WS_URL` 和 `PLUGIN_DEBUG_KEY`，然后用 IDE 调试器启动。

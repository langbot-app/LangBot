# GeneralParsers

Official LangBot parser plugin that extracts structured text from files for KnowledgeEngine plugins (e.g. LangRAG).

## Supported Formats

| Format | MIME Type | Parser |
|--------|-----------|--------|
| PDF | `application/pdf` | PyMuPDF-based layout-aware extraction with tables, page markers, and optional vision enhancement |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx extraction with paragraph/table parsing and optional embedded-image recognition |
| Markdown | `text/markdown` | Convert to HTML, then structured extraction (headings, lists, code blocks, tables) |
| HTML | `text/html` | BeautifulSoup extraction (auto-removes script/style) |
| TXT | `text/plain` | Auto encoding detection (chardet) |
| Images | `image/png`, `image/jpeg`, `image/webp`, `image/gif`, `image/bmp`, `image/tiff` | Direct vision-based recognition when a vision model is configured |

## Architecture

```
┌──────────────────────────────────────────────┐
│  KnowledgeEngine Plugin (e.g. LangRAG)       │
│  Chunk → Embedding → Store → Retrieve        │
└──────────────────┬───────────────────────────┘
                   │ invoke_parser (RPC)
┌──────────────────▼───────────────────────────┐
│          GeneralParsers                      │
│                                              │
│  File bytes → Format detection → Parse       │
│                                              │
│  ParseResult:                                │
│    ├── text: Full extracted text              │
│    ├── sections: Heading-split sections       │
│    │   └── TextSection(content, heading,      │
│    │                   level)                 │
│    └── metadata: filename, MIME type, etc.    │
└──────────────────────────────────────────────┘
```

## Features

- **Optional Vision Model Support** - Configure a vision-capable LLM to OCR scanned PDF pages, recognize embedded PDF/DOCX images, and parse direct image uploads
- **Improved PDF Parsing** - PyMuPDF-based extraction preserves page boundaries, merges tables into output, and emits richer document metadata
- **Isolated PDF Execution** - Every PDF parse runs in its own short-lived process with a hard timeout, so the non-thread-safe PyMuPDF dependency (which keeps module-level page state) can never mix one installation's document text into another's, and a native fault or cancellation only takes down that process
- **Scanned PDF Handling** - Detects likely scanned pages and uses the vision model for OCR when configured
- **Cross-Format Image Recognition** - Embedded PDF/DOCX images and direct image uploads can be turned into inline recognition text for downstream retrieval
- **Header/Footer Filtering** - Repeated page headers and footers are detected and removed from PDF output
- **Section Structure Recognition** - Detects Markdown-style headings (`# ~ ######`) and splits output into leveled sections
- **Table to Markdown** - Tables in PDF/HTML/Markdown are converted to Markdown table format
- **Async Parsing** - File parsing runs in a thread pool to avoid blocking the event loop
- **Auto Encoding Detection** - Uses chardet for encoding detection, supports GBK, UTF-8, etc.
- **Format Fallback** - Unsupported formats are automatically tried as plain text

## Configuration

The plugin exposes two vision-related config items:

- `enable_vision`: enables scanned-page OCR, embedded image recognition, and direct image parsing
- `vision_llm_model_uuid`: a vision-capable LLM used when `enable_vision` is enabled

If vision is disabled or no model is selected, GeneralParsers still works normally, but image understanding falls back to placeholders and PDF parsing uses text/layout extraction only.

## Usage

1. Install this plugin in LangBot
2. Optionally configure a vision model if you want OCR for scanned PDFs, DOCX/PDF image recognition, or direct image parsing
3. When uploading files to a knowledge base, select GeneralParsers as the parser
4. Parse results are automatically passed to the KnowledgeEngine plugin for further processing

## Output Shape

GeneralParsers returns a structured `ParseResult` containing:

- `text`: the full extracted text
- `sections`: heading-aware text sections for chunking strategies that prefer structure
- `metadata`: document metadata such as filename, MIME type, page count, table presence, scanned-page flags, and vision usage stats

Recent PDF parser metadata includes fields such as:

- `page_count`
- `word_count`
- `has_tables`
- `has_scanned_pages`
- `headers_footers_removed`
- `vision_used`
- `vision_tasks_count`
- `vision_scanned_pages_count`
- `vision_images_described_count`
- `vision_failed_count`

## Observability Page

GeneralParsers includes a lightweight WebUI Page named **Parser Observability**.
It shows in-memory parser telemetry for recent parse activity:

- total parses, failures, average/max duration, extracted text characters, sections, and vision tasks
- extension distribution so parser format coverage is easy to inspect
- vision counters for OCR/image-description usage and failures
- recent parse events with file name, MIME type, duration, output size, media flags, and status
- recent parser errors for quick debugging

The page intentionally records only operational metadata. It does not store file
bytes or extracted text.

The Page backend exposes `/snapshot` and `/clear` through the LangBot Page API.
The UI includes `en_US` and `zh_Hans` i18n assets under
`components/pages/i18n/`.

## Development

```bash
pip install -r requirements.txt
cp .env.example .env
```

Configure `DEBUG_RUNTIME_WS_URL` and `PLUGIN_DEBUG_KEY` in `.env`, then launch with your IDE debugger.

### Testing

```bash
python3 -m compileall -q main.py components tests
python3 -m unittest discover -s tests
```

## Contributing

We welcome contributions! Feel free to:

- Submit issues for bugs or feature requests
- Fork the repo and submit pull requests
- Improve documentation or add examples
- Share your ideas and feedback

Star the repo if you find it useful!

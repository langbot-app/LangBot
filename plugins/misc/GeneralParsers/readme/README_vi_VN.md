# GeneralParsers

Plugin phân tích cú pháp (parser) chính thức của LangBot, chuyên trích xuất văn bản có cấu trúc từ các tệp cho các plugin KnowledgeEngine (ví dụ: LangRAG).

## Các định dạng hỗ trợ

| Định dạng | Loại MIME | Bộ phân tích cú pháp |
|-----------|-----------|----------------------|
| PDF | `application/pdf` | Trích xuất theo bố cục dựa trên PyMuPDF với bảng, dấu trang trang và tùy chọn tăng cường thị giác |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Trích xuất bằng python-docx với phân tích cú pháp đoạn văn/bảng và tùy chọn nhận dạng hình ảnh nhúng |
| Markdown | `text/markdown` | Chuyển đổi sang HTML, sau đó trích xuất có cấu trúc (tiêu đề, danh sách, khối mã, bảng) |
| HTML | `text/html` | Trích xuất bằng BeautifulSoup (tự động loại bỏ script/style) |
| TXT | `text/plain` | Tự động phát hiện mã hóa (chardet) |
| Hình ảnh | `image/png`, `image/jpeg`, `image/webp`, `image/gif`, `image/bmp`, `image/tiff` | Nhận dạng trực tiếp dựa trên thị giác khi mô hình thị giác được cấu hình |

## Kiến trúc

```
┌──────────────────────────────────────────────┐
│  KnowledgeEngine Plugin (ví dụ: LangRAG)     │
│  Chunk → Embedding → Store → Retrieve        │
└──────────────────┬───────────────────────────┘
                   │ invoke_parser (RPC)
┌──────────────────▼───────────────────────────┐
│          GeneralParsers                      │
│                                              │
│  File bytes → Format detection → Parse       │
│                                              │
│  ParseResult:                                │
│    ├── text: Toàn bộ văn bản trích xuất      │
│    ├── sections: Các phần chia theo tiêu đề  │
│    │   └── TextSection(nội dung, tiêu đề,    │
│    │                   cấp độ)               │
│    └── metadata: tên tệp, loại MIME, v.v.    │
└──────────────────────────────────────────────┘
```

## Tính năng

- **Hỗ trợ mô hình thị giác tùy chọn** - Cấu hình một LLM có khả năng thị giác để OCR các trang PDF đã quét, nhận dạng hình ảnh PDF/DOCX nhúng và phân tích các hình ảnh tải lên trực tiếp.
- **Cải thiện phân tích cú pháp PDF** - Trích xuất dựa trên PyMuPDF giúp bảo toàn ranh giới trang, gộp các bảng vào đầu ra và cung cấp siêu dữ liệu tài liệu phong phú hơn.
- **Xử lý PDF đã quét** - Phát hiện các trang có khả năng là bản quét và sử dụng mô hình thị giác cho OCR khi được cấu hình.
- **Nhận dạng hình ảnh đa định dạng** - Các hình ảnh nhúng trong PDF/DOCX và hình ảnh tải lên trực tiếp có thể được chuyển thành văn bản nhận dạng nội dòng cho việc truy xuất ở các bước sau.
- **Lọc Header/Footer** - Các đầu trang và chân trang lặp lại được phát hiện và loại bỏ khỏi đầu ra PDF.
- **Nhận dạng cấu trúc phần** - Phát hiện các tiêu đề kiểu Markdown (`# ~ ######`) và chia đầu ra thành các phần có cấp độ.
- **Chuyển đổi Bảng sang Markdown** - Các bảng trong PDF/HTML/Markdown được chuyển đổi sang định dạng bảng Markdown.
- **Phân tích cú pháp bất đồng bộ** - Việc phân tích cú pháp tệp chạy trong một pool luồng để tránh làm tắc nghẽn vòng lặp sự kiện.
- **Tự động phát hiện mã hóa** - Sử dụng chardet để phát hiện mã hóa, hỗ trợ GBK, UTF-8, v.v.
- **Dự phòng định dạng** - Các định dạng không được hỗ trợ sẽ tự động được thử phân tích dưới dạng văn bản thuần túy.

## Cấu hình

Plugin cung cấp một mục cấu hình tùy chọn:

- `vision_llm_model_uuid`: một LLM có khả năng thị giác được sử dụng cho OCR trang quét, nhận dạng hình ảnh PDF/DOCX nhúng và phân tích hình ảnh trực tiếp.

Nếu tùy chọn này để trống, GeneralParsers vẫn hoạt động bình thường, nhưng việc hiểu hình ảnh sẽ chuyển sang sử dụng văn bản giữ chỗ và phân tích cú pháp PDF chỉ sử dụng trích xuất văn bản/bố cục.

## Cách sử dụng

1. Cài đặt plugin này trong LangBot.
2. Tùy chọn cấu hình một mô hình thị giác nếu bạn muốn OCR cho các bản PDF quét, nhận dạng hình ảnh DOCX/PDF hoặc phân tích hình ảnh trực tiếp.
3. Khi tải tệp lên cơ sở kiến thức, hãy chọn GeneralParsers làm bộ phân tích cú pháp.
4. Kết quả phân tích sẽ tự động được chuyển đến plugin KnowledgeEngine để xử lý thêm.

## Cấu trúc đầu ra

GeneralParsers trả về một `ParseResult` có cấu trúc bao gồm:

- `text`: toàn bộ văn bản được trích xuất.
- `sections`: các phần văn bản nhận biết tiêu đề cho các chiến lược phân đoạn ưu tiên cấu trúc.
- `metadata`: siêu dữ liệu tài liệu như tên tệp, loại MIME, số trang, sự hiện diện của bảng, cờ trang quét và thống kê sử dụng thị giác.

Siêu dữ liệu bộ phân tích cú pháp PDF gần đây bao gồm các trường như:

- `page_count` (số trang)
- `word_count` (số từ)
- `has_tables` (có bảng)
- `has_scanned_pages` (có trang quét)
- `headers_footers_removed` (đã loại bỏ đầu/chân trang)
- `vision_used` (đã sử dụng thị giác)
- `vision_tasks_count` (số tác vụ thị giác)
- `vision_scanned_pages_count` (số trang quét thị giác)
- `vision_images_described_count` (số hình ảnh được mô tả thị giác)

## Phát triển

```bash
pip install -r requirements.txt
cp .env.example .env
```

Cấu hình `DEBUG_RUNTIME_WS_URL` và `PLUGIN_DEBUG_KEY` trong `.env`, sau đó khởi chạy với trình gỡ lỗi IDE của bạn.

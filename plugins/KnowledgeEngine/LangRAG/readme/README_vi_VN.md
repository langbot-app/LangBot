#LangRAG

Plugin Công cụ RAG (Thế hệ tăng cường truy xuất) cho LangBot.

Plugin này trình bày cách xây dựng Công cụ tri thức xử lý việc nhập tài liệu và truy xuất vectơ bằng cơ sở hạ tầng tích hợp của LangBot Host (Mô hình nhúng và Cơ sở dữ liệu vectơ).

## Đặc trưng

-**Tích hợp trình phân tích cú pháp bên ngoài**- Ưu tiên nội dung được phân tích cú pháp trước từ plugin Phân tích cú pháp, chẳng hạn như GeneralParsers, bao gồm các phần có cấu trúc và siêu dữ liệu tài liệu
-**Phân tích cú pháp nội bộ dự phòng**- Bao gồm trình phân tích cú pháp tích hợp làm dự phòng khi không có trình phân tích cú pháp bên ngoài nào được định cấu hình
-**Chiến lược nhiều chỉ mục**- Phân chia phẳng, phân chia cha-con, các cặp Hỏi & Đáp do LLM tạo
-**Truy xuất linh hoạt**- Tìm kiếm vectơ, toàn văn bản hoặc kết hợp
-**Viết lại truy vấn**- Chiến lược HyDE, Multi-Query, Step-Back để cải thiện khả năng thu hồi
-**Phân đoạn có thể định cấu hình**- Phân tách ký tự đệ quy với kích thước khối tùy chỉnh và chồng chéo
-**Phân đoạn nhận biết phần**- Khi có sẵn các phần có cấu trúc, việc phân chia sẽ giữ nguyên các tiêu đề, thông tin trang và ranh giới bảng
-**Mở rộng ngữ cảnh**- Tùy chọn nối thêm các đoạn liền kề xung quanh mỗi lần truy cập để có ngữ cảnh truy xuất phong phú hơn
-**Quản lý tài liệu**- Xóa các vectơ được lập chỉ mục theo tài liệu

## Ngành kiến ​​​​trúc

```
┌─────────────────────────────────┐
│         LangBot Core            │
│  (Embedding / VDB / Storage)    │
└──────────┬──────────────────────┘
           │ RPC (IPC)
┌──────────▼──────────────────────┐
│          LangRAG                │
│  ┌───────────────────────────┐  │
│  │    Knowledge Engine       │  │
│  │  Parse → Chunk → Embed   │  │
│  │      → Store / Search    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

## Luồng nhập

LangRAG hiện ưu tiên đầu ra của trình phân tích cú pháp do LangBot Host cung cấp:

1. LangBot đọc file đã tải lên
2. Một plugin Parser như GeneralParsers trích xuất`văn bản`,`phần`và`siêu dữ liệu`
3. LangRAG nhập trực tiếp kết quả có cấu trúc đó
4. Nếu không có đầu ra của trình phân tích cú pháp, LangRAG sẽ quay trở lại trình phân tích cú pháp nội bộ của nó
5. Chiến lược chỉ mục đã chọn xây dựng các đoạn/cặp Hỏi & Đáp
6. LangBot Host tạo các phần nhúng và lưu trữ vectơ

Điều này có nghĩa là LangRAG hoạt động tốt nhất khi được ghép nối với plugin trình phân tích cú pháp bên ngoài.

## Cấu hình

### Sáng tạo cơ sở tri thức

| Tham số | Mô tả | Mặc định |
|----------|-------------|----------|
|`nhúng_model_uuid`| Mô hình nhúng | Bắt buộc |
|`loại_chỉ mục`| Chiến lược chỉ mục:`chunk`,`parent_child`hoặc`qa`|`đoạn`|
|`chunk_size`| Ký tự trên mỗi đoạn | 512 |
|`chồng chéo`| Chồng chéo giữa các khối | 50 |
|`parent_chunk_size`| Kích thước khối gốc (chỉ parent_child) | 2048 |
|`child_chunk_size`| Kích thước khối con (chỉ parent_child) | 256 |
|`qa_llm_model_uuid`| LLM để tạo Q&A (chỉ qa) | - |
|`câu hỏi_per_chunk`| Câu hỏi để tạo mỗi đoạn (chỉ qa) | 1 |

### Truy xuất

| Tham số | Mô tả | Mặc định |
|----------|-------------|----------|
|`top_k`| Số kết quả trả về | 5 |
|`loại_tìm kiếm`| Chế độ tìm kiếm:`vector`,`full_text`hoặc`hybrid`|`vectơ`|
|`truy vấn_rewrite`| Chiến lược viết lại:`off`,`hyde`,`multi_query`hoặc`step_back`|`tắt`|
|`viết lại_llm_model_uuid`| LLM để viết lại truy vấn (khi bật tính năng viết lại) | - |
|`cửa sổ bối cảnh`| Số khối liền kề để nối xung quanh mỗi lần truy cập | 0 |

## Chiến lược chỉ số

-**chunk**- Phân chia phẳng mặc định. Chia tài liệu thành các phần có kích thước cố định và nhúng trực tiếp từng phần. Khi có sẵn các phần của trình phân tích cú pháp, các khối được tạo theo từng phần thay vì làm phẳng toàn bộ tài liệu.
-**parent_child**- Phân chia hai cấp độ. Chia thành các khối cha mẹ lớn, sau đó là các khối con nhỏ hơn. Nhúng các đoạn con nhưng trả về văn bản gốc để có ngữ cảnh phong phú hơn. Khi có sẵn các phần của trình phân tích cú pháp, các phần được sử dụng làm ranh giới gốc tự nhiên.
-**qa**- Các cặp Hỏi & Đáp do LLM tạo. Văn bản phân đoạn, sử dụng LLM để tạo các cặp câu hỏi-câu trả lời trên mỗi phân đoạn và nhúng các câu hỏi. Khi có sẵn các phần của trình phân tích cú pháp, quá trình tạo Hỏi & Đáp cũng sẽ nhận biết theo phần.

## Viết lại truy vấn

-**hyde**- Nhúng tài liệu giả định. Tạo câu trả lời giả định cho truy vấn, sau đó nhúng câu trả lời đó để truy xuất.
-**multi_query**- Tạo 3 biến thể truy vấn, tìm kiếm với mỗi biến thể và hợp nhất các kết quả theo điểm.
-**step_back**- Tạo câu hỏi và tìm kiếm trừu tượng hơn bằng cả truy vấn gốc và truy vấn trừu tượng.

## Ghép nối với GeneralParsers

GeneralParsers hiện là trình phân tích cú pháp được đề xuất cho LangRAG vì nó có thể cung cấp:

- trích xuất PDF sạch hơn
- phần có cấu trúc
- văn bản bảo quản bảng
- siêu dữ liệu cấp tài liệu
- mô tả hình ảnh và OCR tùy chọn thông qua mô hình tầm nhìn

LangRAG sử dụng trực tiếp các đầu ra của trình phân tích cú pháp đó trong quá trình nhập, thường tạo ra các đoạn tốt hơn và chất lượng truy xuất tốt hơn so với trình phân tích cú pháp dự phòng.

## Phát triển

```bash
pip install -r requirements.txt
cp .env.example .env
```

Định cấu hình`DEBUG_RUNTIME_WS_URL`và`PLUGIN_DEBUG_KEY`trong`.env`, sau đó khởi chạy bằng trình gỡ lỗi IDE của bạn.

## Liên kết

- [Tài liệu về LangBot](https://langbot.app/docs/)

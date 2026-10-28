# FastGPTConnector

Truy xuất kiến thức từ các cơ sở kiến thức FastGPT bằng cách sử dụng FastGPT API.

## Giới thiệu về FastGPT

FastGPT là một hệ thống hỏi đáp dựa trên cơ sở kiến thức mã nguồn mở được xây dựng trên các mô hình LLM. Nó cung cấp khả năng xử lý dữ liệu và gọi mô hình có sẵn cho các kịch bản hỏi đáp phức tạp.

## Tính năng

- Tìm kiếm và truy xuất kiến thức từ các bộ dữ liệu/cơ sở kiến thức FastGPT
- Hỗ trợ nhiều chế độ tìm kiếm (embedding, full-text recall, mixed recall)
- Có thể cấu hình ngưỡng tương đồng và giới hạn token
- Tùy chọn xếp hạng lại (re-ranking) để có kết quả tốt hơn
- Tối ưu hóa truy vấn với các mô hình mở rộng

## Cấu hình

Plugin này yêu cầu các tham số cấu hình sau:

### Tham số bắt buộc

- **api_base_url**: URL cơ sở cho FastGPT API
  - Đối với triển khai cục bộ: `http://localhost:3000` (mặc định)
  - Đối với máy chủ từ xa: URL máy chủ của bạn (ví dụ: `https://your-domain.com`)
- **api_key**: Khóa API FastGPT của bạn
  - Định dạng: `fastgpt-xxxxx`
- **dataset_id**: ID của cơ sở kiến thức/bộ dữ liệu FastGPT của bạn

### Tham số tùy chọn

- **limit** (mặc định: 5000): Số lượng token tối đa được truy xuất
- **similarity** (mặc định: 0.0): Điểm tương đồng tối thiểu (0-1)
- **search_mode** (mặc định: embedding): Phương pháp tìm kiếm sẽ sử dụng
  - `embedding`: Tìm kiếm ngữ nghĩa dựa trên vector embedding
  - `fullTextRecall`: Tìm kiếm từ khóa toàn văn
  - `mixedRecall`: Tìm kiếm hỗn hợp kết hợp cả hai phương pháp
- **using_rerank** (mặc định: false): Có sử dụng xếp hạng lại hay không
- **dataset_search_using_extension_query** (mặc định: false): Có sử dụng tối ưu hóa truy vấn hay không
- **dataset_search_extension_model** (tùy chọn): Mô hình để tối ưu hóa truy vấn
- **dataset_search_extension_bg** (tùy chọn): Mô tả ngữ cảnh cho tối ưu hóa truy vấn

## Cách lấy các giá trị cấu hình

### Lấy khóa API FastGPT của bạn

1. Truy cập vào instance FastGPT của bạn (ví dụ: `http://localhost:3000`)
2. Điều hướng đến phần quản lý API hoặc cài đặt
3. Tạo hoặc sao chép khóa API của bạn (định dạng: `fastgpt-xxxxx`)

### Lấy ID bộ dữ liệu của bạn

1. Trong FastGPT, đi tới danh sách cơ sở kiến thức của bạn
2. Nhấp vào một cơ sở kiến thức để xem chi tiết
3. ID bộ dữ liệu có thể được tìm thấy trong URL hoặc trang chi tiết bộ dữ liệu

## Tài liệu tham khảo API

Plugin này sử dụng FastGPT Dataset Search Test API:
- Endpoint: `POST /api/core/dataset/searchTest`
- Tài liệu: https://doc.fastgpt.io/docs/introduction/development/openapi/dataset

## Các phương pháp tìm kiếm

### Tìm kiếm Embedding (Embedding Search)
Sử dụng độ tương đồng ngữ nghĩa dựa trên các vector embedding. Tốt nhất để hiểu ý định truy vấn và tìm nội dung liên quan về mặt ngữ nghĩa.

### Truy hồi Toàn văn (Full-Text Recall)
Tìm kiếm toàn văn dựa trên từ khóa truyền thống. Tốt nhất để tìm các kết quả khớp chính xác và các thuật ngữ cụ thể.

### Truy hồi Hỗn hợp (Mixed Recall)
Kết hợp cả hai phương pháp tìm kiếm embedding và toàn văn. Cung cấp kết quả cân bằng với cả sự hiểu biết về ngữ nghĩa và so khớp từ khóa.

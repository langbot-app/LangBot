# RAGFlowConnector

Truy xuất kiến ​​thức từ hoặc lưu trữ tệp vào cơ sở kiến ​​thức RAGFlow bằng API RAGFlow.

## Giới thiệu về RAGFlow

RAGFlow là một công cụ RAG (Thế hệ tăng cường truy xuất) mã nguồn mở dựa trên sự hiểu biết sâu sắc về tài liệu. Nó cung cấp khả năng trả lời câu hỏi trung thực với các trích dẫn có cơ sở từ nhiều dữ liệu có định dạng phức tạp khác nhau.

## Đặc trưng

- Truy xuất các khối kiến thức từ bộ dữ liệu/cơ sở kiến thức RAGFlow
- Tải lên và nhập tệp vào bộ dữ liệu RAGFlow với tính năng phân tích cú pháp tự động
- Hỗ trợ nhiều tập dữ liệu trong một truy vấn
- Ngưỡng tương tự có thể cấu hình và trọng số vectơ
- Tìm kiếm kết hợp từ khóa và vector tương tự
- Tự động kích hoạt xây dựng biểu đồ tri thức GraphRAG sau khi nhập
- Tự động kích hoạt tóm tắt phân cấp RAPTOR sau khi nhập
- Xác thực ID tập dữ liệu khi tạo cơ sở tri thức
- Trả về kết quả với siêu dữ liệu phong phú bao gồm điểm tương đồng về thuật ngữ và vectơ

## Cấu hình

Plugin này yêu cầu các tham số cấu hình sau:

### Tham số bắt buộc (Cài đặt tạo)

-**api_base_url**: URL cơ sở cho API RAGFlow
  - Để triển khai cục bộ:`http://localhost:9380`(mặc định)
  - Đối với máy chủ từ xa: URL máy chủ của bạn (ví dụ:`http://your-domain.com:9380`)
-**api_key**: Khóa API RAGFlow từ phiên bản RAGFlow của bạn
-**dataset_ids**: ID tập dữ liệu được phân tách bằng dấu phẩy để tìm kiếm
  - Định dạng:`"dataset_id1,dataset_id2,dataset_id3"`
  - Ví dụ:`"b2a62730759d11ef987d0242ac120004,a3b52830859d11ef887d0242ac120005"`

### Tham số tùy chọn (Cài đặt tạo)

-**auto_graphrag**(mặc định: false): Tự động kích hoạt xây dựng biểu đồ tri thức GraphRAG sau khi nhập tệp
-**auto_raptor**(mặc định: false): Tự động kích hoạt tóm tắt phân cấp RAPTOR sau khi nhập tệp

### Tham số tùy chọn (Cài đặt truy xuất)

-**top_k**(mặc định: 1024): Số lượng kết quả truy xuất tối đa
-**similarity_threshold**(mặc định: 0,2): Điểm tương tự tối thiểu (0-1)
-**vector_similarity_weight**(mặc định: 0,3): Trọng số cho độ tương tự của vectơ trong tìm kiếm kết hợp (0-1)
-**page_size**(mặc định: 30): Số lượng kết quả trên mỗi trang
-**keyword**(mặc định: false): Sử dụng LLM để trích xuất từ khóa khỏi truy vấn nhằm tăng cường khả năng truy xuất
-**rerank_id**: Xếp hạng lại ID mô hình được định cấu hình trong RAGFlow (ví dụ:`BAAI/bge-reranker-v2-m3`)
-**use_kg**(mặc định: false): Cho phép truy xuất biểu đồ tri thức

## Cách lấy giá trị cấu hình

### Lấy khóa API RAGFlow của bạn

1. Truy cập phiên bản RAGFlow của bạn (ví dụ:`http://localhost:9380`)
2. Điều hướng đến phần**Cài đặt người dùng**>**API**
3. Tạo hoặc sao chép khóa API của bạn (định dạng:`ragflow-xxxxx`)

### Lấy ID tập dữ liệu của bạn

1. Trong RAGFlow, hãy chuyển đến danh sách cơ sở kiến thức/tập dữ liệu của bạn
2. Nhấp vào tập dữ liệu để xem chi tiết
3. ID tập dữ liệu thường được hiển thị trong URL hoặc chi tiết tập dữ liệu
4. Đối với nhiều tập dữ liệu, hãy thu thập tất cả ID và nối chúng bằng dấu phẩy

## Tham chiếu API

Plugin này sử dụng các API RAGFlow sau:
- Truy xuất:`POST /api/v1/retrieval`
- Tải lên tài liệu:`POST /api/v1/datasets/{dataset_id}/documents`
- Phân tích tài liệu:`POST /api/v1/datasets/{dataset_id}/chunks`
- Xóa tài liệu:`DELETE /api/v1/datasets/{dataset_id}/documents`
- Cấu trúc GraphRAG:`POST /api/v1/datasets/{dataset_id}/run_graphrag`
- Cấu trúc RAPTOR:`POST /api/v1/datasets/{dataset_id}/run_raptor`
- Liệt kê các tập dữ liệu (xác thực):`GET /api/v1/datasets`
- Tài liệu: https://ragflow.io/docs/dev/http_api_reference

## Phương pháp truy xuất

RAGFlow sử dụng phương pháp truy xuất kết hợp:
-**Tương tự từ khóa**: So khớp dựa trên từ khóa truyền thống
-**Tương tự vectơ**: Tương tự về mặt ngữ nghĩa bằng cách sử dụng các phần nhúng
-**Kết hợp có trọng số**: Kết hợp cả hai phương pháp với trọng số có thể định cấu hình
-**Biểu đồ tri thức**: Truy xuất dựa trên biểu đồ tùy chọn cho các câu trả lời nhận biết mối quan hệ
-**Sắp xếp lại**: Mô hình sắp xếp lại tùy chọn để cải thiện chất lượng kết quả

Tham số`vector_similarity_weight`kiểm soát sự cân bằng giữa các phương thức từ khóa và vectơ.

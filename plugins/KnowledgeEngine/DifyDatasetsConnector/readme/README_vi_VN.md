#DifyDatasetsConnector

Truy xuất kiến ​​thức từ hoặc lưu trữ tệp vào cơ sở kiến ​​thức Dify bằng API Dify.

## Cấu hình

Vui lòng thêm cơ sở kiến ​​thức bên ngoài vào LangBot và chọn "DifyDatasetsConnector" làm loại trình truy xuất kiến ​​thức.

### Cài đặt tạo (được đặt khi tạo cơ sở kiến ​​thức)

-**api_base_url**: URL cơ sở cho API Dify
  - Đối với Dify Cloud:`https://api.dify.ai/v1`(mặc định)
  - Đối với các phiên bản tự lưu trữ: URL máy chủ của bạn (ví dụ:`http://localhost/api`hoặc`https://your-domain.com/api`)
-**dify_apikey**: Khóa API Dify từ phiên bản Dify của bạn
-**dataset_id**: ID của cơ sở dữ liệu/cơ sở kiến thức Dify của bạn

### Cài đặt truy xuất (có thể điều chỉnh cho mỗi truy vấn)

-**search_method**(mặc định: ngữ nghĩa_search): Phương thức tìm kiếm sẽ sử dụng
  -`keyword_search`: Tìm kiếm dựa trên từ khóa
  -`semantic_search`: Tìm kiếm tương tự về mặt ngữ nghĩa (mặc định)
  -`full_text_search`: Tìm kiếm toàn văn
  -`hybrid_search`: Tìm kiếm kết hợp ngữ nghĩa và toàn văn
-**top_k**(mặc định: 5): Số lượng kết quả truy xuất tối đa
-**score_threshold_enabled**(mặc định: false): Có bật tính năng lọc ngưỡng điểm hay không
-**score_threshold**(mặc định: 0,5): Điểm phù hợp tối thiểu (0-1), chỉ hiển thị khi bật ngưỡng điểm
-**reranking_enable**(mặc định: false): Bật tính năng sắp xếp lại để cải thiện chất lượng kết quả. Mô hình sắp xếp lại được tự động tìm nạp từ cài đặt tập dữ liệu Dify của bạn - trước tiên hãy định cấu hình mô hình sắp xếp lại trong bảng điều khiển Dify

## Cách lấy giá trị cấu hình

### Lấy khóa API Dify của bạn

1. Truy cập https://cloud.dify.ai/
2. Điều hướng đến trang cơ sở kiến thức của bạn
3. Nhấp vào "TRUY CẬP API" ở thanh bên trái
4. Tạo hoặc sao chép khóa API của bạn từ phần "Khóa API"

### Lấy ID tập dữ liệu của bạn

1. Trong danh sách cơ sở kiến thức Dify, nhấp vào cơ sở kiến thức của bạn
2. ID tập dữ liệu có trong URL:`https://cloud.dify.ai/datasets/{dataset_id}`
3. Hoặc bạn có thể tìm thấy nó trong trang tài liệu API trong cơ sở kiến thức của bạn

### Cấu hình sắp xếp lại

1. Trong bảng điều khiển Dify, hãy chuyển đến cài đặt tập dữ liệu của bạn
2. Kích hoạt tính năng sắp xếp lại và chọn mô hình sắp xếp lại (ví dụ:`cohere/rerank-v3.5`)
3. Lưu cài đặt
4. Trong LangBot, bật nút chuyển đổi "Bật xếp hạng lại" - plugin sẽ tự động sử dụng mô hình được định cấu hình trong Dify

## Tham chiếu API

Plugin này sử dụng API bộ dữ liệu Dify:
- Truy xuất:`POST /v1/datasets/{dataset_id}/retrieve`
- Thông tin tập dữ liệu:`GET /v1/datasets/{dataset_id}`
- Tải lên tài liệu:`POST /v1/datasets/{dataset_id}/document/create-by-file`
- Xóa tài liệu:`DELETE /v1/datasets/{dataset_id}/documents/{document_id}`
- Tài liệu: https://docs.dify.ai/

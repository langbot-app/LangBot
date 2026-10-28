# WeKnora Agent

`agent-id` là tùy chọn trong cả hai chế độ. Nếu không đặt, `chat` dùng `builtin-quick-answer` và `agent` dùng `builtin-smart-reasoning`; giá trị rỗng tường minh không gửi ID. ID đã lưu không bị thay thế. `knowledge-base-ids` là ID WeKnora từ xa cho cả hai chế độ, không phải UUID LangBot.

## Tổng quan

Chạy tác nhân WeKnora hoặc ứng dụng trò chuyện kho tri thức dưới dạng LangBot Runner.

## Thông tin gói

- **Runner ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **Phiên bản**: `0.1.2`
- **Kho mã nguồn**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## Khả năng chính

- **Đã bật**: `streaming`
- **Không khai báo**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## Cấu hình

| Trường | Kiểu | Bắt buộc | Mặc định |
| --- | --- | --- | --- |
| `base-url` | `string` | Có | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | Có | Trống |
| `app-type` | `select` | Có | `agent` |
| `agent-id` | `string` | Không | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | Không | `[]` |
| `web-search-enabled` | `boolean` | Không | false |
| `advanced-settings` | `boolean` | Không | false |
| `timeout` | `integer` | Không | `120` |
| `base-prompt` | `string` | Không | `请回答用户的问题。` |

## Quyền Host

- **`storage`**: `plugin`

## Cài đặt và sử dụng

1. Cài đặt plugin từ chợ plugin LangBot.
2. Chọn Runner ID bên dưới trong bộ chọn Runner của Pipeline.
3. Điền thông tin kết nối theo bảng và lưu giá trị nhạy cảm bằng trường secret trong giao diện quản trị.

## Bảo mật và giới hạn

- Runner chỉ được dùng tài nguyên LangBot đã cấp quyền cho lần chạy hiện tại.
- Tính sẵn sàng, khả năng mô hình và giới hạn tốc độ phụ thuộc vào dịch vụ bên ngoài.
- Xem hành vi nâng cao và giới hạn riêng của sản phẩm trong README tiếng Trung ở thư mục gốc hoặc README_en_US.md tiếng Anh.

# DeerFlow Agent

## Tổng quan

Chạy tác nhân DeerFlow LangGraph dưới dạng LangBot Runner.

## Thông tin gói

- **Runner ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **Phiên bản**: `0.1.2`
- **Kho mã nguồn**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## Khả năng chính

- **Đã bật**: `streaming`, `multimodal input`
- **Không khai báo**: `tool calling`, `knowledge retrieval`, `interrupt`

## Cấu hình

| Trường | Kiểu | Bắt buộc | Mặc định |
| --- | --- | --- | --- |
| `api-base` | `string` | Có | `http://127.0.0.1:2026` |
| `api-key` | `secret` | Không | Trống |
| `auth-header` | `secret` | Không | Trống |
| `assistant-id` | `string` | Có | `lead_agent` |
| `advanced-settings` | `boolean` | Không | false |
| `model-name` | `string` | Không | Trống |
| `thinking-enabled` | `boolean` | Không | false |
| `plan-mode` | `boolean` | Không | false |
| `subagent-enabled` | `boolean` | Không | false |
| `max-concurrent-subagents` | `integer` | Không | `3` |
| `timeout` | `integer` | Không | `300` |
| `recursion-limit` | `integer` | Không | `1000` |

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

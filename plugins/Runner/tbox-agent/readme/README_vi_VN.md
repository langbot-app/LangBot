# Tbox Agent

`remove-think` chỉ nhận giá trị boolean (mặc định `false`). Đặt `true` để ẩn suy luận và khối `<think>`, kể cả khi chia đoạn luồng, đồng thời giữ câu trả lời và nội dung công cụ.

## Tổng quan

Chạy ứng dụng Ant Tbox dưới dạng LangBot Runner.

## Thông tin gói

- **Runner ID**: `plugin:langbot-team/TboxAgent/default`
- **Phiên bản**: `0.1.0`
- **Kho mã nguồn**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent)

## Khả năng chính

- **Đã bật**: `streaming`, `multimodal input`
- **Không khai báo**: `tool calling`, `knowledge retrieval`, `interrupt`

## Cấu hình

| Trường | Kiểu | Bắt buộc | Mặc định |
| --- | --- | --- | --- |
| `api-key` | `secret` | Có | Trống |
| `app-id` | `string` | Có | Trống |
| `timeout` | `number` | Không | `120` |

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

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-bot` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-bot` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-bot` uses `conversation.bot_id` (or Host runtime `bot_id` when there is no conversation), exactly, without a prefix.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.

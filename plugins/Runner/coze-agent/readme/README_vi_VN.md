# Coze Agent

`remove-think` chỉ nhận giá trị boolean (mặc định `false`). Đặt `true` để ẩn suy luận và khối `<think>`, kể cả khi chia đoạn luồng, đồng thời giữ câu trả lời và nội dung công cụ.

## Tổng quan

Chạy bot Coze dưới dạng LangBot Runner.

## Thông tin gói

- **Runner ID**: `plugin:langbot-team/CozeAgent/default`
- **Phiên bản**: `0.1.2`
- **Kho mã nguồn**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/coze-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/coze-agent)

## Khả năng chính

- **Đã bật**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`
- **Không khai báo**: `interrupt`

## Cấu hình

| Trường | Kiểu | Bắt buộc | Mặc định |
| --- | --- | --- | --- |
| `api-key` | `secret` | Có | Trống |
| `bot-id` | `string` | Có | Trống |
| `api-base` | `string` | Có | `https://api.coze.cn` |
| `advanced-settings` | `boolean` | Không | false |
| `auto-save-history` | `boolean` | Không | true |
| `timeout` | `number` | Không | `120` |
| `langbot-assets-enabled` | `boolean` | Không | false |
| `langbot-assets-gateway-host` | `string` | Không | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | Không | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | Không | `60` |
| `langbot-assets-token-ttl` | `integer` | Không | `3600` |
| `langbot-assets-input-name` | `string` | Không | `langbot_asset_run_token` |

## Quyền Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`
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
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the Query launcher for Coze into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.

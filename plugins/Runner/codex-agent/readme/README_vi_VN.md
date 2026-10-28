# Codex Agent

## Tổng quan

Chạy Codex CLI dưới dạng LangBot Runner.

## Thông tin gói

- **Runner ID**: `plugin:langbot-team/CodexAgent/default`
- **Phiên bản**: `0.1.9`
- **Kho mã nguồn**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent)

## Khả năng chính

- **Đã bật**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **Không khai báo**: `multimodal input`, `interrupt`

## Cấu hình

| Trường | Kiểu | Bắt buộc | Mặc định |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | Không | false |
| `daemon-host` | `string` | Không | `127.0.0.1` |
| `daemon-port` | `integer` | Không | `8768` |
| `daemon-token` | `secret` | Không | Trống |
| `location` | `select` | Có | `local` |
| `workspace` | `string` | Không | Trống |
| `advanced-settings` | `boolean` | Không | false |
| `command` | `string` | Không | `codex` |
| `args-json` | `string` | Không | `[]` |
| `env-json` | `string` | Không | `{}` |
| `ssh-target` | `string` | Không | Trống |
| `ssh-port` | `integer` | Không | `22` |
| `daemon-id` | `string` | Không | Trống |
| `timeout` | `integer` | Không | `300` |
| `streaming` | `boolean` | Không | true |
| `reuse-session` | `boolean` | Không | true |
| `approval-policy` | `select` | Không | `never` |
| `sandbox-mode` | `select` | Không | `danger-full-access` |
| `knowledge-bases` | `knowledge-base-multi-selector` | Không | `[]` |
| `langbot-assets-enabled` | `boolean` | Không | true |
| `mcp-bridge-transport` | `select` | Không | `auto` |
| `mcp-servers-json` | `string` | Không | `[]` |

## Quyền Host

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## Cài đặt và sử dụng

1. Cài đặt plugin từ chợ plugin LangBot.
2. Chọn Runner ID bên dưới trong bộ chọn Runner của Pipeline.
3. Điền thông tin kết nối theo bảng và lưu giá trị nhạy cảm bằng trường secret trong giao diện quản trị.

## Bảo mật và giới hạn

- Cấu hình mặc định khởi động Codex với `approvalPolicy=never` và `sandbox=danger-full-access`, đồng thời không chờ phê duyệt tương tác. Chỉ sử dụng với không gian làm việc đáng tin cậy và tài khoản hệ điều hành bị giới hạn quyền.
- Runner chỉ được dùng tài nguyên LangBot đã cấp quyền cho lần chạy hiện tại.
- Tính sẵn sàng, khả năng mô hình và giới hạn tốc độ phụ thuộc vào dịch vụ bên ngoài.
- Xem hành vi nâng cao và giới hạn riêng của sản phẩm trong README tiếng Trung ở thư mục gốc hoặc README_en_US.md tiếng Anh.


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。

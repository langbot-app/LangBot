# ACP Runner

## Tổng quan

Chạy tác nhân lập trình tương thích Agent Client Protocol dưới dạng LangBot Runner.

## Thông tin gói

- **Runner ID**: `plugin:langbot-team/ACPAgentRunner/default`
- **Phiên bản**: `0.1.4`
- **Kho mã nguồn**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner)

## Khả năng chính

- **Đã bật**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `steering`
- **Không khai báo**: `interrupt`

## Cấu hình

| Trường | Kiểu | Bắt buộc | Mặc định |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | Không | false |
| `daemon-host` | `string` | Không | `127.0.0.1` |
| `daemon-port` | `integer` | Không | `8766` |
| `daemon-token` | `secret` | Không | Trống |
| `provider` | `select` | Có | `claude-code` |
| `location` | `select` | Có | `local` |
| `workspace` | `string` | Không | Trống |
| `advanced-settings` | `boolean` | Không | false |
| `ssh-target` | `string` | Không | Trống |
| `daemon-id` | `string` | Không | Trống |
| `daemon-connect-timeout` | `integer` | Không | `30` |
| `ssh-port` | `integer` | Không | `22` |
| `ssh-identity-file` | `string` | Không | Trống |
| `acp-command` | `string` | Không | Trống |
| `knowledge-bases` | `knowledge-base-multi-selector` | Không | `[]` |
| `langbot-assets-enabled` | `boolean` | Không | true |
| `langbot-assets-mode` | `select` | Không | `auto` |
| `langbot-assets-gateway-host` | `string` | Không | `127.0.0.1` |
| `langbot-assets-gateway-port` | `integer` | Không | `0` |
| `langbot-assets-gateway-public-url` | `string` | Không | Trống |
| `langbot-assets-token-ttl` | `integer` | Không | `3600` |
| `timeout` | `integer` | Không | `300` |
| `reuse-session` | `boolean` | Không | true |
| `env-json` | `text` | Không | Trống |
| `ssh-connect-timeout` | `integer` | Không | `10` |
| `ssh-extra-options` | `string` | Không | Trống |
| `startup-timeout` | `integer` | Không | `30` |
| `initialize-timeout` | `integer` | Không | `120` |
| `create-session-if-missing` | `boolean` | Không | true |
| `streaming` | `boolean` | Không | true |
| `append-run-scope-prompt` | `boolean` | Không | true |
| `mcp-servers-json` | `text` | Không | Trống |

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


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。

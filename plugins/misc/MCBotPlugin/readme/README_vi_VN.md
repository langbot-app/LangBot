# MCBotPlugin

Plugin LangBot cho các nhóm chat máy chủ Minecraft: liên kết máy chủ với nhóm, truy vấn trạng thái máy chủ theo thời gian thực và người chơi trực tuyến, đồng thời thống kê thời gian chơi của từng người.

> Đây là phiên bản chuyển đổi của [MCBotPlugin](https://github.com/langbot-app/MCBotPlugin) cũ (xây dựng cho QChatGPT) sang LangBot plugin SDK mới. Lưu trữ được thay từ MongoDB sang KV storage tích hợp sẵn của plugin (không cần cơ sở dữ liệu bên ngoài), truy vấn trạng thái Minecraft được thay từ `mctools` đồng bộ sang `mcstatus` bất đồng bộ, và việc lấy mẫu thời gian chơi nền được thay từ thread sang tác vụ asyncio.

## Tính năng

- **Liên kết máy chủ**: mỗi nhóm có thể liên kết một máy chủ Minecraft (Java Edition)
- **Truy vấn trạng thái**: MOTD, phiên bản, số người trực tuyến và danh sách người chơi theo thời gian thực
- **Thống kê thời gian chơi**: một tác vụ nền lấy mẫu người chơi trực tuyến và tổng hợp thời gian trực tuyến của từng người trong bất kỳ khoảng thời gian nào

## Lệnh

| Lệnh | Mô tả | Quyền |
| --- | --- | --- |
| `!mcbot` | Hiển thị trợ giúp | Mọi người |
| `!mcbot bind <địa chỉ[:cổng]>` | Liên kết máy chủ với nhóm này | Quản trị viên |
| `!mcbot unbind` | Hủy liên kết máy chủ | Quản trị viên |
| `!mcbot status` | Hiển thị trạng thái máy chủ và người chơi trực tuyến | Mọi người |
| `!mcbot time [phút]` | Hiển thị thống kê thời gian chơi (mặc định 1440 phút = 24 giờ) | Mọi người |

> Quản trị viên được xác định bởi cấu hình `admins` của LangBot (`{launcher_type}_{launcher_id}`).

## Cấu hình

| Khóa | Mô tả | Mặc định |
| --- | --- | --- |
| `track_interval` | Khoảng thời gian lấy mẫu người chơi trực tuyến (giây), tối thiểu 15 | 60 |
| `ping_timeout` | Thời gian chờ ping máy chủ (giây) | 10 |

## Phụ thuộc

- [`mcstatus`](https://github.com/py-mine/mcstatus) — Truy vấn trạng thái máy chủ Minecraft

## Lưu trữ dữ liệu

Thông tin liên kết và bản ghi trực tuyến được lưu trong KV storage tích hợp sẵn của plugin LangBot; không cần MongoDB. Bản ghi trực tuyến được giữ lại 14 ngày theo mặc định.

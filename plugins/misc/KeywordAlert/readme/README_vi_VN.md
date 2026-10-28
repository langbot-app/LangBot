# Cảnh báo từ khóa

Giám sát tin nhắn trò chuyện nhóm để tìm từ khóa cụ thể và nhận thông báo tin nhắn riêng tư ngay lập tức.

## Đặc trưng

- 🔔 Giám sát từ khóa theo thời gian thực trên các cuộc trò chuyện nhóm
- 📋 Danh sách từ khóa có thể định cấu hình (được phân tách bằng dấu phẩy)
- 🎯 Giám sát các nhóm cụ thể hoặc tất cả các nhóm
- 🤖 Chọn bot nào gửi thông báo
- ⏱️ Thời gian hồi chiêu để ngăn chặn cảnh báo spam
- 🔤 Tùy chọn kết hợp phân biệt chữ hoa chữ thường

## Nó hoạt động như thế nào

1. Định cấu hình các từ khóa bạn muốn theo dõi (ví dụ:`lỗi,khẩn cấp,trợ giúp`)
2. Đặt ID người dùng/phiên của bạn làm quản trị viên để nhận thông báo
3. Khi ai đó gửi tin nhắn có chứa từ khóa trong nhóm được giám sát, bạn sẽ nhận được thông báo tin nhắn riêng tư với ngữ cảnh đầy đủ

## Cấu hình

| Tùy chọn | Mô tả | Mặc định |
|---|---|---|
| Từ khóa | Từ khóa được phân tách bằng dấu phẩy để theo dõi | (bắt buộc) |
| ID nhóm | ID nhóm được phân tách bằng dấu phẩy (trống = tất cả) | Tất cả các nhóm |
| ID phiên quản trị viên | Ai nhận được thông báo | (bắt buộc) |
| Cảnh báo Bot | Bot nào gửi cảnh báo | Có sẵn đầu tiên |
| Phân biệt chữ hoa chữ thường | Khớp phân biệt chữ hoa chữ thường | Tắt |
| Thời gian hồi chiêu | Số giây giữa các cảnh báo từ khóa giống nhau cho mỗi nhóm | 60 |

## Định dạng cảnh báo

```
🔔 关键词告警
━━━━━━━━━━━━━━
关键词: urgent
群组: 123456789
发送者: 987654321
━━━━━━━━━━━━━━
Hey, this is urgent, the server is down!
```

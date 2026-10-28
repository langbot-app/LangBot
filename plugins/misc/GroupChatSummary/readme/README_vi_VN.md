# GroupChatSummary

Tóm tắt tin nhắn trò chuyện nhóm bằng LLM. Không bao giờ bỏ lỡ các cuộc thảo luận quan trọng nữa.

## Tính năng

- **Thu thập tin nhắn**: Tự động ghi lại tất cả tin nhắn trong nhóm
- **Tóm tắt thủ công**: Sử dụng lệnh `!summary` để có tóm tắt tức thì
- **Tóm tắt dựa trên thời gian**: Tóm tắt tin nhắn từ N giờ qua
- **Công cụ LLM**: AI có thể gọi công cụ tóm tắt khi người dùng hỏi "tôi đã bỏ lỡ điều gì?"
- **Tự động tóm tắt**: Tùy chọn kích hoạt tóm tắt sau khi tích lũy N tin nhắn
- **Lưu trữ vĩnh viễn**: Lịch sử tin nhắn vẫn tồn tại sau khi khởi động lại plugin

## Lệnh

| Lệnh | Mô tả |
|---------|-------------|
| `!summary [count]` | Tóm tắt N tin nhắn gần đây (mặc định: 100) |
| `!summary hours <N>` | Tóm tắt tin nhắn từ N giờ qua |
| `!summary status` | Hiển thị trạng thái bộ đệm tin nhắn |
| `!summary clear` | Xóa các tin nhắn đã lưu trữ |

## Cấu hình

| Tùy chọn | Mặc định | Mô tả |
|--------|---------|-------------|
| Max Messages | 500 | Số lượng tin nhắn tối đa được lưu trữ cho mỗi nhóm |
| Default Summary Count | 100 | Số lượng tin nhắn được tóm tắt theo mặc định |
| Auto Summary | Tắt | Tự động tóm tắt sau mỗi N tin nhắn |
| Auto Summary Threshold | 200 | Số lượng tin nhắn trước khi tự động kích hoạt |
| Language | Chinese | Ngôn ngữ đầu ra của bản tóm tắt |

## Cách hoạt động

1. Plugin lắng nghe tất cả tin nhắn trong nhóm và lưu trữ chúng vào bộ nhớ (được lưu vào bộ nhớ vĩnh viễn)
2. Khi được kích hoạt (lệnh, cuộc gọi công cụ hoặc tự động), nó định dạng các tin nhắn và gửi chúng đến LLM đã cấu hình của bạn
3. LLM tạo một bản tóm tắt có cấu trúc với các chủ đề chính, quyết định và các mục hành động

## Ví dụ

```
User: !summary 50
Bot: ⏳ Đang tóm tắt 50 tin nhắn...
Bot: 📋 Tóm tắt trò chuyện nhóm

**Thảo luận dự án**
- Nhóm đã quyết định sử dụng React cho frontend
- Hạn chót của backend API đã được chuyển sang thứ Sáu tới

**Mục hành động**
- @Alice: Chuẩn bị bản thiết kế mẫu trước thứ Tư
- @Bob: Thiết lập quy trình CI/CD
```
